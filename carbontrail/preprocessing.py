import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from scipy.signal import savgol_filter

# Duplicates Filter

'''There are often many duplicates entries for a given timestamp. They must be removed. 
We determine which entry to keep based on the value of the barometric altitude. 
The entry with the barometric altitude that is the closest to the temporally interpolated value between 
the previous and subsequent points is kept.'''

def duplicate_filter(flight,interpolate_on='alt_baro'):
    new = flight.copy()
    if interpolate_on not in flight.columns:
        _ = interpolate_on
        rank_order = [x for x in ['alt_baro','alt_geom','lat','lon'] if x in flight.columns]
        interpolate_on = rank_order[0]
        print(f'{_} not present in the given flight dataframe. Duplicate filter will run interpolation on the {interpolate_on} column instead.')
    new['interpolated'] = new[interpolate_on]
    duplicated_mask = flight.duplicated(subset=['postime'],keep=False)
    new.loc[duplicated_mask,'interpolated'] = np.nan
    new.set_index('postime',inplace=True)
    new['interpolated'] = new['interpolated'].interpolate(method='time')
    new.reset_index(inplace=True)
    new['interp_diff'] = abs(new[interpolate_on]-new.interpolated)
    final = new.sort_values('interp_diff',ascending=True).drop_duplicates('postime').sort_index().drop(columns=['interpolated','interp_diff']).reset_index(drop=True)
    return final

# Resampling

def resample(flight,freq='5S',retain_str_columns=False):
    '''Resamples the given flight dataframe according to the frequency provided (5 seconds by default).
    As a first step, this function checks if there are are duplicate values in the postime column. These must be removed first.
    If retain_str_columns is True, the dataframe will be returned with all the columns of the given dataframe. This increases computation time by around 3x.
    If retain_str_columns is False, for increased efficiency, the non-numeric columns are not included in the returned dataframe 
    
    Returns a resampled dataframe.'''
    if retain_str_columns:
        ocols = flight.columns
        temp = flight.select_dtypes(exclude=['number','datetime'])
    flight = flight.select_dtypes(include=['number','datetime'])
    if flight.postime.duplicated().any():
        print('The given "flight" DataFrame contains duplicate rows. Pass the DataFrame through the "duplicate_filter" function to clean it before passing to this one.')
    flight = flight.set_index('postime')
    oidx = pd.Index(flight.index)
    nidx = pd.date_range(oidx.min().ceil('S'), oidx.max().floor('S'), freq=freq)
    new_df = flight.reindex(oidx.union(nidx)).interpolate(method='time').reindex(nidx)
    new_df = new_df.reset_index().rename(columns={'index':'postime'})
    if retain_str_columns:
        temp = temp.mode(axis=0)
        temp = temp.reindex(temp.index.union(nidx)).ffill().reindex(nidx)
        new_df = pd.merge(new_df,temp,left_on='postime',right_index=True,how='inner')
        new_df = new_df[ocols]
    return new_df

# Filters

def sg_filter(flight,target_col,window_length,polyorder,damping=0):
    '''Applies a Savinsky-Golay filter to the target column (target_col) of the given DataFrame (flight).
    As a first step, this function checks if there are are duplicate values in the postime column. These must be removed first.
    
    -damping should be a value from 0-1 and is used to damp the change from the original value.
    A value of 0 will not take into account the original value.
    A value of 1 will take only the original value.
    A value of 0.5 will take the mean of the new and original values.
    
    Returns a Pandas Series with an index identical to that of the given DataFrame.'''
    if flight.postime.duplicated().any():
        print('The given "flight" DataFrame contains duplicate rows. Pass the DataFrame through the "duplicate_filter" function to clean it before passing to this one.')
    else:
        track_profile = flight.copy()

        # Savinsky-Golay filter
        result = savgol_filter(track_profile[target_col],13,5)
        result = track_profile[target_col]*damping + result*(1-damping)
        return result

def mean_filter(flight,target_col,window_length,damping=0):
    '''Applies a mean filter to the target column (target_col) of the given DataFrame (flight).
    This replace each value in the target_col with the mean of a rolling window with given window_length
    As a first step, this function checks if there are are duplicate values in the postime column. These must be removed first.
    
    -damping should be a value from 0-1 and is used to damp the change from the original value.
    A value of 0 will not take into account the original value.
    A value of 1 will take only the original value.
    A value of 0.5 will take the mean of the new and original values.
    
    Returns a Pandas Series with an index identical to that of the given DataFrame.'''
    if flight.postime.duplicated().any():
        print('The given "flight" DataFrame contains duplicate rows. Pass the DataFrame through the "duplicate_filter" function to clean it before passing to this one.')
    else:
        track_profile = flight.copy()

        window_arm = int(window_length/2)
        # Mean filter
        result = track_profile[target_col]
        for i in np.arange(1,window_arm+1):
            result = result + track_profile[target_col].shift(-i).fillna(track_profile[target_col].iloc[-1]) + track_profile[target_col].shift(i).fillna(track_profile[target_col].iloc[0])
        result = result/window_length
        result.iloc[0:window_arm] = track_profile[target_col].iloc[0:window_arm]
        result.iloc[-window_arm:] = track_profile[target_col].iloc[-window_arm:]
        # result.iloc[0:window_arm] = result.iloc[window_arm]
        # result.iloc[-window_arm:] = result.iloc[-window_arm-1]

        result = track_profile[target_col]*damping + result*(1-damping)
        return result

def tempinter_filter(flight,target_col,damping=0):
    '''Applies a temporal interpolation filter to the target column (target_col) of the given DataFrame (flight).
    This replace each value in the target_col with the temporally interpolated value between the preceding and subsequent values in the column
    As a first step, this function checks if there are are duplicate values in the postime column. These must be removed first.
    
    -damping should be a value from 0-1 and is used to damp the change from the original value.
    A value of 0 will not take into account the original value.
    A value of 1 will take only the original value.
    A value of 0.5 will take the mean of the new and original values.
    
    Returns a Pandas Series with an index identical to that of the given DataFrame.'''
    if flight.postime.duplicated().any():
        print('The given "flight" DataFrame contains duplicate rows. Pass the DataFrame through the "duplicate_filter" function to clean it before passing to this one.')
    else:
        track_profile = flight.copy()

        # Calculate the time step of each entry
        track_profile['postime_shift'] = track_profile.postime.shift(-1)
        tdelt = track_profile.apply(lambda x: (x.postime_shift-x.postime).seconds,axis=1) #seconds
        track_profile['postime_shift_neg'] = track_profile.postime.shift(1)
        tdelt_neg = track_profile.apply(lambda x: (x.postime-x.postime_shift_neg).seconds,axis=1) #seconds

        # Temporal interpolation filter
        result = track_profile[target_col].shift() + (track_profile[target_col].shift(-1) - track_profile[target_col].shift())*(tdelt_neg)/(tdelt+tdelt_neg)
        result.iloc[0] = track_profile[target_col].iloc[0]
        result.iloc[-1] = track_profile[target_col].iloc[-1]

        result = track_profile[target_col]*damping + result*(1-damping)
        return result

def derive_acceleration(flight,target_tas):
    '''Calculates the acceleration of the given DataFrame (flight) from the target true airspeed column (target_tas).
    As a first step, this function checks if there are are duplicate values in the postime column. These must be removed first
    
    Returns a Pandas Series with an index identical to that of the given DataFrame.'''
    if flight.postime.duplicated().any():
        print('The given "flight" DataFrame contains duplicate rows. Pass the DataFrame through the "duplicate_filter" function to clean it before passing to this one.')
    else:
        track_profile = flight.copy()

        # Calculate the time step of each entry
        track_profile['postime_shift'] = track_profile.postime.shift(-1)
        tdelt = track_profile.apply(lambda x: (x.postime_shift-x.postime).seconds,axis=1) #seconds

        result = (track_profile[target_tas].shift(-1)-track_profile[target_tas])*0.514444/tdelt # (1 kt = 0.514444 ms2)
        result[len(track_profile)-1] = 0
        return result

# ROCD filtering

def derive_rocd(flight,target_alt):
    '''Calculates the ROCD of the given DataFrame (flight) from the target altitude column (target_alt).
    As a first step, this function checks if there are are duplicate values in the postime column. These must be removed first
    
    Returns a Pandas Series with an index identical to that of the given DataFrame.'''
    if flight.postime.duplicated().any():
        print('The given "flight" DataFrame contains duplicate rows. Pass the DataFrame through the "duplicate_filter" function to clean it before passing to this one.')
    else:
        track_profile = flight.copy()

        # Calculate the time step of each entry
        track_profile['postime_shift'] = track_profile.postime.shift(-1)
        tdelt = track_profile.apply(lambda x: (x.postime_shift-x.postime).seconds,axis=1) #seconds

        result = (track_profile[target_alt].shift(-1)-track_profile[target_alt])/tdelt*60 # (1 kt = 0.514444 ms2)
        result[len(track_profile)-1] = 0
        return result

