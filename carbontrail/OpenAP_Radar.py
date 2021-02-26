import numpy as np
import pandas as pd
from .aircraft import AircraftModel
from .aircraft import AircraftTrackState
from .preprocessing import *
import warnings
from IPython.core.debugger import set_trace


attr_map = {'fphase':'phase',
            'h_p':'alt_baro',
            'vtas':'tas_filtered',
            'mach':'mach',
            'rocd':'baro_rate_derived',
            'atas':'atas_ms2_derived',
            'flight_distance':'distance',
            'flight_time':'time',
            # 'temp':'temperature',
            # 'p':'p',
            # 'rho':'rho',
            'vcas':'vcas',
            'drag':'drag',
            'fflow':'fuel',
            'm':'mass'}

def assign_fphase(flight,rocd_col='baro_rate',window_length=None):
    '''Assigns a flight phase to each row based on the ROCD of the subsequent rows. 
    The number of subsequent rows to consider is determined by window_length.
    The function defaults to consider the ROCD of the aircraft for the next 1.5 minutes.
    '''
    flight = flight.copy()
    if not window_length:
        avg_seconds = flight.postime.diff().mean().seconds
        window_length = int((1.5*60)/avg_seconds)
    rocds = np.array(flight[rocd_col]).reshape(len(flight),1)
    for i in range(window_length-1):
        rocds = np.append(rocds,np.array(flight[rocd_col].shift(-i).fillna(flight[rocd_col].iloc[-1])).reshape(len(flight),1),axis=1)
    climb_mask = np.all(rocds>=500,axis=1)
    cruise_mask = np.all((rocds>-500)&(rocds<500),axis=1)
    descent_mask = np.all(rocds<=-500,axis=1)
    flight['phase'] = np.nan
    flight.loc[climb_mask,'phase'] = 'Climb'
    flight.loc[cruise_mask,'phase'] = 'Cruise'
    flight.loc[descent_mask,'phase'] = 'Descent'
    flight.phase = flight.phase.ffill()
    flight.phase = flight.phase.bfill()
    return flight

def extract_state(state_entry,aircraft_state):
    for state_attr in ['fphase','h_p','vtas','mach','rocd','atas']:
        setattr(aircraft_state,state_attr,state_entry[attr_map[state_attr]])

def fill_track_profile(track_profile,i,aircraft_state):
    for key,value in attr_map.items():
        track_profile.loc[i,value] = getattr(aircraft_state,key)

def evaluate_track_states(filtered_profile,ac_type,tow=None):
    try:
        aircraft_model = AircraftModel(ac_type)
    except RuntimeError as e:
        aircraft_model = AircraftModel('A320')
        warnings.warn(e.__str__()+' A320 used as proxy')
    aircraft_state = AircraftTrackState(aircraft_model)
    track_profile = filtered_profile.copy()
    if tow is None:
        MTOW = aircraft_state.aircraft_model.properties['limits']['MTOW']
        OEW = aircraft_state.aircraft_model.properties['limits']['OEW'] 
        tow = MTOW + 0.75*(MTOW-OEW) # [kg]
    
    aircraft_state.m = tow
    aircraft_state.flight_time = 0
    for i in track_profile.index:
        extract_state(track_profile.loc[i],aircraft_state)
        aircraft_state.update_state()
        fill_track_profile(track_profile,i,aircraft_state)
        if i != track_profile.index[0]:
            aircraft_state.m -= aircraft_state.fflow * track_profile.postime.diff().at[i].seconds/60
        # set_trace()
    return track_profile

def evaluate_track(unfiltered_profile,ac_type,tow=None,filter_type=tempinter_filter,**filter_kwds):
    track_profile = unfiltered_profile.copy()
    track_profile['tas_filtered'] = filter_type(track_profile,'tas',**filter_kwds)
    track_profile['atas_ms2_derived'] = derive_acceleration(track_profile,'tas_filtered')
    track_profile['alt_baro_filtered'] = filter_type(track_profile,'alt_baro',**filter_kwds)
    track_profile['baro_rate_derived'] = derive_rocd(track_profile,'alt_baro_filtered')    
    track_profile = assign_fphase(track_profile,rocd_col='baro_rate_derived')

    for col in [x for x in attr_map.values() if x not in track_profile.columns]:
        track_profile[col] = np.nan
    track_profile = evaluate_track_states(track_profile,ac_type,tow)
    return track_profile
