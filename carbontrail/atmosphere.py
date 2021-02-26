import math 

class Atmosphere():
    def __init__(self,**kwargs):    
        self.temp_delta=0 # BADA-3.1.1: "Temperature differential at MSL. It is the difference in atmospheric temperature at MSL between a given non-standard atmosphere and ISA."
        self.delta_p=0 # BADA-3.1.1: "Pressure differential at MSL. It is the difference in atmospheric pressure at MSL between a given non-standard atmosphere and ISA."
        
        # Mean Sea Level (MSL) standard atmosphere conditions: (BADA-3.1.1)
        self.temp_0 = 288.15 #Standard atmospheric temeprature at MSL [K]
        self.p_0 = 101325 #Standard atmsopheric pressure at MSL [Pa]
        self.rho_0 = 1.225 #Standard atmospheric density at MSL [kg/m^3]
        self.a_0 = 340.294 #Speed of sound [m/s]
        self.h_p_trop = 11000 # Geopotential pressure altitude of tropopause [m] BADA-3.1.2
        
        # Physical constants: (BADA-3.1.2)
        self.kappa = 1.4 #Adiabatic index of air
        self.gas_const = 287.05287 #Real gas constant for air [m^2/(K*s^2)]
        self.g_0 = 9.80665 #Gravitational acceleration [m/s^2]
        self.beta_temp_bt = -0.0065 #ISA temperature gradient with altitude below tropopause (_bt) [K/m]
        self.mu = (self.kappa - 1)/self.kappa
        self.temp_isa_trop = self.temp_0 + self.beta_temp_bt*self.h_p_trop
        for key,value in kwargs.items():
            setattr(self,key,value)

    def temperature(self,h_p):
        """Returns ISA standard atmosphere temperature [K] at pressure altitude (h_p [ft]) of aircraft state passed to function. 
        This function also sets the standard ISA atmosphere tropopause temperature as global variable,
        'self.temp_isa_trop'. From BADA-3.1.2.a"""
        #Conversion to meters is required for use in the following formulas (1ft = 0.3048m).
        h_p = 0.3048*h_p
        
        temp_trop = self.temp_0 + self.temp_delta + self.beta_temp_bt*self.h_p_trop
        if h_p < 11000: #below tropopause [m]
            temp = self.temp_0 + self.temp_delta + self.beta_temp_bt*h_p
        elif h_p >= 11000: #above tropopause [m]
            temp = temp_trop
        return temp #[K]

    def pressure(self,h_p,temp=None):
        """Returns ISA standard atmosphere pressure [Pa] at pressure altitiude (h_p [ft]) of aircraft state passed to function.
        If temp is None, it will be evaluated for ISA conditions at the given altitude. temp must be given in Kelvin.  
        From BADA-3.1.2.b"""
        #Conversion to meters is required for use in the following formulas (1ft = 0.3048m).
        h_p = 0.3048*h_p 
        if not temp:
            temp = self.temperature(h_p)

        temp_trop = self.temp_0 + self.temp_delta + self.beta_temp_bt*self.h_p_trop
        p_trop = self.p_0*((temp_trop-self.temp_delta)/self.temp_0
                                    )**(-self.g_0/(self.beta_temp_bt*self.gas_const)) #pressure at tropopause (h_p = 11000 m)
        if h_p < 11000: #below tropopause [m]
            p = self.p_0*((temp-self.temp_delta)/self.temp_0)**(
                -self.g_0/(self.beta_temp_bt*self.gas_const))
        elif h_p == 11000:
            p = p_trop
        elif h_p > 11000: #above tropopause [m]
            p = p_trop*math.exp(-self.g_0/(self.gas_const*self.temp_isa_trop)*(h_p-self.h_p_trop))
        return p #[Pa]

    def density(self,temp=None,p=None):
        """temp must be in Kelvin and p must be in Pa. Output is in kg/m^3.  From BADA-3.1.2.c."""
        if not temp:
            temp = self.temp
        if not p:
            p = self.p
        rho = p/(self.gas_const*temp)
        return rho #[kg/m^3]

    def update(self,h_p):
        """Returns temp (temperature [K]), p (pressure [Pa]), and rho (density [kg/m^3]) at 
        pressure altitude (h_p [ft]) of aircraft state passed to function. self.temp_delta must be in Kelvin (or Celsius). From BADA-3.1.2"""
        self.temp = self.temperature(h_p) # K
        self.p = self.pressure(h_p) # Pa
        self.rho = self.density() # kg/m^2
        self.a = math.sqrt(self.kappa*self.gas_const*self.temp) # m/s

    def vtas_to_mach(self,vtas):
        """Returns Mach number corresponding to the vtas [kt] of aircraft state passed to function at given temperature, temp [K].
        From BADA-3.1.2.f."""
        #Conversion to m/s is required for use in the following formula. (1 kt = 0.514444 m/s)
        vtas *= 0.514444
        mach = vtas/math.sqrt(self.kappa*self.gas_const*self.temp)
        return mach 

    def mach_to_vtas(self,Mach):
        """Returns vtas [kt] corresponding to the Mach number of aircraft state passed to function at given temperature, temp [K].
        From BADA-3.1.2.f."""
        vtas = Mach*math.sqrt(self.kappa*self.gas_const*self.temp) # vtas calculated in this step is in m/s
        #vtas converted to Kt. (1 kt = 0.514444 m/s)
        vtas /= 0.514444
        return vtas # [kt]

    def cas_to_tas(self,vcas):
        """Converts vcas [kt] to vtas [kt] at given local atmospheric pressure (p [Pa]) and density (rho [kr/m^3]).
        From BADA-3.1.2.e."""
        #Conversion to m/s is required for use in the following formula. (1 kt = 0.514444 m/s)
        vcas *= 0.514444 
        
        vtas = (2/self.mu*self.p/self.rho*((1+self.p_0/self.p*(
            (1+self.mu/2*self.rho_0/self.p_0*vcas**2)**(
                1/self.mu)-1))**self.mu-1))**0.5
        
        #Convert vtas from m/s to kt before returning.
        vtas /= 0.514444
        return vtas #[kt]
        
    def tas_to_cas(self,vtas):
        """Converts vtas [kt] to vcas [kt] at given local atmospheric pressure (p [Pa]) and density (rho [kr/m^3]). """
        #Conversion to m/s is required for use in the following formula. (1 kt = 0.514444 m/s)
        vtas *= 0.514444 
        
        vcas = (2/self.mu*self.p_0/self.rho_0*((1+self.p/self.p_0*((1+self.mu/2*self.rho/self.p*vtas**2)**(
                1/self.mu)-1))**self.mu-1))**0.5
        
        #Convert vcas from m/s to kt before returning.
        vcas /= 0.514444
        return vcas #[kt]