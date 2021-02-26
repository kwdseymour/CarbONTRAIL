# coding: utf-8

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import sys
import os
from carbontrail import *
from carbontrail.database_tools import *
from carbontrail.OpenAP_Radar import *
from openap import prop
import json

import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Output, Input

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

if os.path.isfile('carbontrail/FEAT_Radar.py'):
    feat_available = True
    from carbontrail.FEAT_Radar import *
else:
    feat_available = False

# HOST = '10.0.0.34' 
HOST = config['mariadb_host'] # This must be the IP address of the device running the SQL server on the LAN (can be set to 'localhost' if on the same device)
ac_database = pd.read_csv('carbontrail/data_inputs/opensky_aircraft_database.csv',usecols=['icao24','registration','manufacturername','model','typecode','built'])
ac_database = ac_database.dropna(subset=['icao24','typecode']).set_index('icao24')

available_airlines = {'Swiss':'SWR','KLM':'KLM','EasyJet':'EZY','Ryanair':'RYR','Lufthansa':'DLH','Air Malta':'AMC','British Airways':'BAW','Air France':'AFR','Iberia':'IBE'}
token = 'pk.eyJ1Ijoia3dkc2V5bW91ciIsImEiOiJja2lyYmJidHkwMzhiMnRwZDB6ZGp0bTZlIn0.7fDKtGWJ_6DDnnQwDDhWzw'

app = dash.Dash()
app.layout = html.Div([
    dcc.Dropdown(
        id='airline_select',
        options=[{'label': key, 'value': value} for key,value in available_airlines.items()],
        value='SWR'),
    dcc.Graph(id='live-map',animate=True),
    dcc.Interval(
        id='map-update',
        interval=15000,
        n_intervals=0,),
    html.Div([
            dcc.Markdown("""
                **Selected Flight**
            """),
            html.Pre(id='click-data',),
        ], className='three columns'),
    dcc.Graph(id='live-graph',animate=True),
    # dcc.Interval(
    #     id='graph-update',
    #     interval=15000,
    #     n_intervals=0,),
])

@app.callback(Output('live-map', 'figure'),
              [Input('map-update', 'n_intervals'),
               Input('airline_select', 'value')])
def update_map(n,airline_id):

    statement = "SELECT flight FROM global_aircraft WHERE postime > (UTC_TIMESTAMP() - INTERVAL 15 MINUTE)"
    callsigns = get_dataframe(statement=statement,host=HOST)
    callsigns = list(callsigns.flight)
    callsigns = [x for x in callsigns if airline_id in x]
    callsigns = ",".join([f"'{x}'" for x in callsigns])

    statement = f"SELECT flight,hex,r,t,postime,lat,lon FROM global_aircraft WHERE flight IN ({callsigns}) AND postime > (UTC_TIMESTAMP() - INTERVAL 5 HOUR)"
    current = get_dataframe(statement=statement,host=HOST)

    track_profile = current.copy()

    track_profile['time'] = track_profile.postime.diff().apply(lambda x: x.seconds/60).cumsum()
    track_profile.loc[0,'time'] = 0

    colors = ['#4285F4']
    fig = px.line_mapbox(track_profile, lat='lat', lon='lon', color='flight', color_discrete_sequence=colors, hover_data=['flight','postime','lat','lon'], custom_data=['flight','hex','r','t'], height=500, width=1200)#, zoom=2)

    # fig.update_layout(mapbox_style="stamen-terrain", mapbox_center_lat = track_profile.lat.mean(), mapbox_zoom=3,
    #     margin={"r":0,"t":0,"l":0,"b":0})
    fig.update_layout(mapbox_style="dark", mapbox_accesstoken=token, mapbox_center_lat = track_profile.lat.mean(), mapbox_zoom=3,
        margin={"r":0,"t":0,"l":0,"b":0})

    return fig

@app.callback(Output('live-graph', 'figure'),
              [Input('live-map', 'clickData')])
def update_graph(clickData):
    if clickData is None:
        return dash.no_update
    else:
        callsign = clickData['points'][0]['customdata'][0]
        ac_type = clickData['points'][0]['customdata'][3]
        statement = f"SELECT * FROM global_aircraft WHERE flight = '{callsign}' AND postime > (UTC_TIMESTAMP() - INTERVAL 5 HOUR)"
        current = get_dataframe(statement=statement,host=HOST)

        flight = duplicate_filter(current)
        flight_res = resample(flight,'15S')
        try:
            aircraft_prop = prop.aircraft(ac_type)
        except RuntimeError as e:
            aircraft_prop = prop.aircraft('A320')
        MTOW = aircraft_prop['limits']['MTOW']
        OEW = aircraft_prop['limits']['OEW'] 
        tow = MTOW + 0.75*(MTOW-OEW) # [kg]
        
        openap_profile = evaluate_track(unfiltered_profile=flight_res,ac_type=ac_type,tow=tow,filter_type=mean_filter,**{'damping':0,'window_length':7})
        prof_list = [openap_profile]
        if feat_available:
            feat_profile = compute_track_fuel(flight=flight_res,ac_type=ac_type,TOW=tow,filter_type=mean_filter,**{'damping':0,'window_length':7})
            prof_list.append(feat_profile)

        for tp in prof_list:
            tp.loc[0,'time'] = 0
            tp['time'] = tp.postime.diff().apply(lambda x: x.seconds/60).cumsum()
            tp['co2_cumsum'] = (tp.time.diff()*tp.fuel*3.16).cumsum() # [kg]
            tp.loc[0,'co2_cumsum'] = 0
        
            # This is to prevent an abnormality where the fuel increases sharply at the end. A more appropriate solution should be found
            tp.at[len(tp)-1,'fuel'] = tp.at[len(tp)-2,'fuel']

        titles = ['Barometric altitude [ft]','True air speed [kts]','Mach number','Drag [kN]','Fuel consumption [kg/min]','CO2 emissions [kg]']
        fig = make_subplots(rows=2, cols=3, horizontal_spacing=0.1,subplot_titles=titles)
        fig.append_trace({'x':openap_profile.time,'y':openap_profile.alt_baro,'name':'Altitude','mode':'lines','type':'scatter','line':{'color':"#4285F4"}},1,1)
        fig.append_trace({'x':openap_profile.time,'y':openap_profile.tas_filtered,'name':'True air speed','mode':'lines','type':'scatter','line':{'color':"#4285F4"}},1,2)
        fig.append_trace({'x':openap_profile.time,'y':openap_profile.mach,'name':'Mach','mode':'lines','type':'scatter','line':{'color':"#4285F4"}},1,3)
        fig.append_trace({'x':openap_profile.time,'y':openap_profile.drag/1e3,'name':'Drag','mode':'lines','type':'scatter','line':{'color':"#F4B400"}},2,1)
        fig.append_trace({'x':openap_profile.time,'y':openap_profile.fuel,'name':'Fuel consumption','mode':'lines','type':'scatter','line':{'color':"#DB4437"}},2,2)
        fig.append_trace({'x':openap_profile.time,'y':openap_profile.co2_cumsum,'name':'CO2 emissions','mode':'lines','type':'scatter','line':{'color':"#0F9D58"}},2,3)
        if feat_available:
            fig.append_trace({'x':feat_profile.time,'y':feat_profile.drag/1e3,'name':'Drag','mode':'lines','type':'scatter','line':{'color':"#F4B400",'dash':'dash'}},2,1)
            fig.append_trace({'x':feat_profile.time,'y':feat_profile.fuel,'name':'Fuel consumption','mode':'lines','type':'scatter','line':{'color':"#DB4437",'dash':'dash'}},2,2)
            fig.append_trace({'x':feat_profile.time,'y':feat_profile.co2_cumsum,'name':'CO2 emissions','mode':'lines','type':'scatter','line':{'color':"#0F9D58",'dash':'dash'}},2,3)
        for axis_num in ['1','2','3','4','5','6']:
            fig['layout']['xaxis'+axis_num]['title']='Flight time [min]'
            fig['layout']['xaxis'+axis_num]['title']['font']={'size':15}
            fig['layout']['xaxis'+axis_num]['tickfont']={'size':15}
            fig['layout']['yaxis'+axis_num]['tickfont']={'size':15}
            fig['layout']['xaxis'+axis_num]['range']=[0,openap_profile.time.max()*1.05]
        for i in fig['layout']['annotations']: # Updates subplot title fonts
            i['font'] = dict(size=20)
        fig['layout']['yaxis1']['range']=[0,openap_profile.alt_baro.max()*1.05]
        fig['layout']['yaxis2']['range']=[0,openap_profile.tas_filtered.max()*1.05]
        fig['layout']['yaxis3']['range']=[0,openap_profile.mach.max()*1.05]
        if feat_available:
            max_feat_drag = feat_profile.drag.max()
            max_feat_fuel = feat_profile.fuel.max()
            max_feat_cco2 = feat_profile.co2_cumsum.max()
        else:
            max_feat_drag=0; max_feat_fuel=0; max_feat_cco2=0
        fig['layout']['yaxis4']['range']=[0,max(max_feat_drag,openap_profile.drag.max())/1e3*1.05]
        fig['layout']['yaxis5']['range']=[0,max(max_feat_fuel,openap_profile.fuel.max())*1.05]
        fig['layout']['yaxis6']['range']=[0,max(max_feat_cco2,openap_profile.co2_cumsum.max())*1.05]
        fig.update_layout(showlegend=False,template='plotly_dark',height=700, width=1200)

        return fig

@app.callback(
    Output('click-data', 'children'),
    [Input('map-update','n_intervals'),
    Input('live-map', 'clickData'),
    ])
def display_click_data(n,clickData):
    if clickData is None:
        return dash.no_update
    else:
        callsign = clickData['points'][0]['customdata'][0]
        hex_code = clickData['points'][0]['customdata'][1]
        ac_type = clickData['points'][0]['customdata'][3]
        grammar = 'n' if ac_type[0].lower() in 'aeiou()' else ''
        if hex_code in ac_database.index:
            manufacturer = str(ac_database.at[hex_code,'manufacturername'])
            if manufacturer=='nan':
                manufacturer = ''
            modelname = str(ac_database.at[hex_code,'model'])
            if modelname=='nan':
                modelname=''
            modelname = modelname.replace(manufacturer+' ','')
            try:
                build_year = ac_database.at[hex_code,'built'][:4]
                build_year_string = f' manufactured in {build_year}'
            except:
                build_year_string = ''
            if len(manufacturer) * len(modelname) > 0:
                grammar = 'n' if manufacturer[0].lower() in 'aeiou()' else ''
                return_val = f'The selected flight ({callsign}) is operated with a{grammar} {manufacturer} {modelname}{build_year_string}.'
            else:
                return_val = f'The selected flight ({callsign}) is operated with a{grammar} {ac_type}{build_year_string}.'
        else:
            return_val = f'The selected flight ({callsign}) is operated with a{grammar} {ac_type}.'
        
        try:
            # If the aircraft type is not available in the OpenAP library, this will throw an Exception and print a corresponding message.
            prop.aircraft(ac_type)
        except RuntimeError as e:
            return_val += '\n'+(e.__str__()+' A320 used as proxy in the OpenAP model.')

        return return_val

app.run_server(debug=True)  # Turn off reloader if inside Jupyter