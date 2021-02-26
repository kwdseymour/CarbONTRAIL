import pandas as pd 
import numpy as np
import warnings
from openap import prop, Drag, FuelFlow
from .atmosphere import Atmosphere
from .exceptions import UndefinedState

class AircraftModel():
    '''This holds all relevent aircraft parameters for flight profile simulation.
    
    Default load factor (load_factor) and passenger-to-freight factor (ptf_factor) values are set as attributes according 
    to analysis performed for global performance in 2018. These values and all other model parameters can be overidden
    by passing values as keyword arguments to "model_parameters".
    
    An AircraftModel object is a required "profile_generator" function input.'''
    def __init__(self,name,engine='default',**model_parameters):
        self.name = name
        self.properties = prop.aircraft(name)
        if engine == 'default':
            self.engine = prop.engine(self.properties['engine']['default'])
        else:
            self.engine = prop.engine(engine)
        self.drag = Drag(ac=self.name)
        self.fuel_flow = FuelFlow(ac=self.name,eng=self.engine['name'])


class AircraftTrackState():
    '''Objects of this class are passed through the profile generation process and hold the aircraft state data.
    It requires an AircraftModel object as an input because it also serves as a pointer to the aircraft parameters
    stored as attributes of the AircraftModel object.'''
    def __init__(self,aircraft_model,**atmos_kwargs):
        self.aircraft_model = aircraft_model
        self.atmosphere = Atmosphere(**atmos_kwargs)
        self.flight_distance=0
        self.fphase = None
        self.m = None
        self.h_p = None
        self.vtas = None
        self.mach = None
        self.rocd = None
        self.atas = None
    # def __getattr__(self,attr): 
    #     '''Inherets attributes from the AircraftModel object'''
    #     return getattr(self.aircraft_model,attr)
    
    def configuration(self):
        """Returns flap configuration ["Take-Off","Initial Climb","Cruise","Approach","Landing"] based on 
        h_p (pressure altitude [ft]), fphase (flight phase), and VCAS (calibrated airspeed [kt]) of 
        aircraft state."""

        # Below values are geopotential pressure altitude in feet: (BADA-5.6)
        H_max_TO = 400 # Maximum altitude threshold for take-off
        H_max_IC = 2000 # Maximum altitude threshold for initial climb
        H_max_AP = 8000 # Maximum altitude threshold for approach
        H_max_LD = 3000 # Maximum altitude threshold for landing
        
        if self.fphase == "Climb" or self.fphase == "Take-Off":
            if self.h_p < H_max_TO:
                conf = "Take-Off"
            elif self.h_p < H_max_IC:
                conf = "Initial Climb"
            else:
                conf = "Cruise"

        elif self.fphase in ['Descent','Approach','Landing','Taxi-In']:
            if self.h_p >= H_max_AP:
                conf = "Cruise"
            elif self.h_p >= H_max_LD: 
                conf = "Approach"
            else:
                conf = "Landing"
                
        elif self.fphase == "Cruise":
            conf = "Cruise"
        else:
            raise Exception(f'Invalid flight phase assigned: {self.fphase}')
        return conf

    def thrust(self):
    
        #Conversion from kts to m/s is required for use in the following formula. (1 kt = 0.514444 m/s)
        vtas = 0.514444*self.vtas #[m/s]
        #Convert rocd from ft/min to m/s (1 m = 3.28084 ft)
        rocd = self.rocd/60/3.28084 # [m/s] (1 m = 3.28084 ft)
        thrust = self.drag + self.m*self.atmosphere.g_0*rocd/vtas + self.m*self.atas
        thrust = max(thrust,0)
        return thrust #[N]

    def find_path_angle(self):
        #Conversion to m/s is required for use in the following formula. (1 kt = 0.514444 m/s)
        vtas = 0.514444*self.vtas #[m/s]
        #Convert rocd from ft/min to m/s (1 m = 3.28084 ft)
        rocd = self.rocd/60/3.28084 # [m/s] (1 m = 3.28084 ft)
        path_angle = np.degrees(np.arcsin(rocd/vtas)) #degrees
        assert path_angle < 20
        return path_angle      

    def update_state(self):
        '''Updates the aircraft state attributes for the current flight segment based on the current altitude.
        Aircraft state is derived from the following attributes, all of which must be current to provide accurate results:
        - h_p (altitude)
        - fphase(flight phase)
        - vtas (true air speed [kts])
        - rocd (rate of climb or descent [ft/min])
        - atas (acceleration of true air speed [kts])
        - m (aircraft mass [kg])
        - mach (Mach number) (this will only be applied if OpenAP is updated to incorporate wave drag)
        '''
    
        self.atmosphere.update(self.h_p)
        self.vcas = self.atmosphere.tas_to_cas(self.vtas)
        self.conf = self.configuration()
        if self.conf == 'Cruise':
            if self.aircraft_model.drag.wave_drag:
                # Calculate a new vtas such that the Open AP Drag.clean() function will incorporate the given aircraft Mach number
                warnings.warn('OpenAP is now calculating wave drag. The given aircraft state Mach number is now being used in a convoluted way to calculate it.')
                vtas = self.atmosphere.mach_to_vtas(self.mach)
            else:
                vtas = self.vtas
            self.drag = self.aircraft_model.drag.clean(mass=self.m, tas=vtas, alt=self.h_p, path_angle=self.find_path_angle())
        else:
            fla_dict = {'Take-Off':20,'Initial Climb':10,'Approach':15,'Landing':30} # These values are somewhat arbitrarily determined using some info from "Sun, J., Hoekstra, J. M., & Ellerbroek, J. (n.d.). Aircraft Drag Polar Estimation Based on a Stochastic Hierarchical Model.""
            lgr_dict = {'Take-Off':True,'Initial Climb':False,'Approach':False,'Landing':True}
            self.drag = self.aircraft_model.drag.nonclean(mass=self.m, tas=self.vtas, alt=self.h_p, flap_angle=fla_dict[self.conf], path_angle=self.find_path_angle(), landing_gear=lgr_dict[self.conf])
        self.thr = self.thrust()
        self.fflow = self.aircraft_model.fuel_flow.at_thrust(acthr=self.thr,alt=self.h_p)*60 # convert kg/s to kg/min
