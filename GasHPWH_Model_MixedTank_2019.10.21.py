# -*- coding: utf-8 -*-
"""
Created on Mon Apr 01 12:53:33 2019

This script represents a model of GTI's gas HPWH. It is currently capable of being run using draw profile information from
either CBECC-Res ot GTI's field monitoring project. It also currently has two modes, one where it simply predicts the performance
of a device over a given draw profile, and a second where it compares the performance of the device to that which is observed
in the measured data.

The model is broken into several different setions. The sections are as follows:
Import Statements: Imports various python packages as necessary
Inputs: This is the most important section for the user. It includes inputs that a) Inform the model of the input data,
-(Either CBECC-Res draw profile or GTI field data), b) Determine whether it is running a simulation or comparing to measured 
-data (Comparing to measured data should probably only be used for model validation purposes), and c) Define the parameters of 
-the gas HPWH and the operating conditions
Constant Declarations and Calculations: This section contains constants such as the specific heat of water, as well as 
-calculations needed for the project (For instance, conversions from SI units to IP)
Modeling: This section performs the calculations necessary to model the gas HPWH and, if instructed to in Inputs, compare the
-results to the measured data. This is the guts of the model, and the most important portion for users who with to truly
-understand how it functions or modify it

@author: pgrant
"""

#%%--------------------------IMPORT STATEMENTS--------------------------------

import pandas as pd
import numpy as np
from bokeh.plotting import figure, output_file, save, gridplot
from bokeh.models import LassoSelectTool, WheelZoomTool, BoxZoomTool, ResetTool
import os
import time

#%%--------------------------INPUTS-------------------------------------------

#These first two variables describe the data you're using to input your hot water draw profile. The first variable provides the path
#to the data set itself. This means you should fill in the path with the specific location of your data file. Note that this 
#can be done directly on SharePoint, but it works much better if you sync the folder to your hard drive
#The second variable states the source of the draw profile data. Right now the model is capable of handling CBECC-Res draw profiles,
#generated using our scripts, and data from GTI's field study on these devices. The comment after Type_DrawProfile states
#the possible options

Type_DrawProfile = 'GTI_Field' #Used to calculate the duration of the dataframe. Current options include: CBECC, GTI_Field
#The following parameters describe the draw profile to use. Currently they're only applicable for CBECC type simulations
Bedrooms = 1 #Number of bedrooms used in the simulation
FloorArea_Conditioned = 605 #Conditioned floor area of the dwelling used in the simulation
WeatherSource = 'CA' #Type of weather file to use in the simulation. Currently only supports CA
ClimateZone = '12' #CA climate zone to use in the simulation
Temperature_Supply_WaterHeater = 125 #Supply temperature of the water heater, in deg F
Timestep = 5 #Timestep to use in the draw profile and simulation, in minutes

if Type_DrawProfile == 'CBECC':
    Path_DrawProfile = os.path.dirname(__file__) + os.sep + 'Data\Draw_Profiles\Profile_Single_' + str(Bedrooms) + 'BR_CFA=' + str(FloorArea_Conditioned) + '_Weather=' + WeatherSource + ClimateZone + '_Setpoint=' + str(Temperature_Supply_WaterHeater) + '.csv'
else:
    Path_DrawProfile = os.path.dirname(__file__) + os.sep + 'Data\GTI\Calibration Dataset 1.0 for Frontier - Site 4 (May-June 2019) CONFIDENTIAL.csv'


#Set this = 1 if you want to compare model predictions to measured data results. This is useful for model validation and error
#checking. If you want to only input the draw profile and see what the data predicts, set this = 0. Note that =1 mode causes the
#calculations to take much longer
Compare_To_MeasuredData = 1

#These inputs are a series of constants describing the conditions of the simulation. Many of them are overwritten with measurements
#if Compare_To_MeasuredData = 1. The constants describing the gas HPWH itself come from communications with Alex of GTI, and may
#need to be updated if he sends new values
Temperature_Tank_Initial = 135 #Deg F, initial temperature of water in the storage tank
Temperature_Tank_Set = 135 #Deg F, set temperature of the HPWH
Temperature_Tank_Set_Deadband = 35 #Deg F, deadband on the thermostat
Temperature_Water_Inlet = 40 #Deg F, inlet water temperature in this simulation
Temperature_Ambient = 68 #deg F, temperature of the ambient air, placeholder for now
Volume_Tank = 73 #gal, volume of water held in the storage tank
Coefficient_JacketLoss = 5.75 #W/K, based on e-mail from Alex Fridyland on 29 Mar 2019
Power_Backup = 0 #W, electricity consumption of the backup resistance elements
Threshold_Activation_Backup = 95 #Deg F, backup element operates when tank temperature is below this threshold. Note that this operate at the same time as the heat pump
Threshold_Deactivation_Backup = 115 #Deg F, sets the temperature when the backup element disengages after it has been engaged
FiringRate_HeatPump = 2930.72 #W, heat consumed by the heat pump
ElectricityConsumption_Active = 158.5 #W, electricity consumed by the fan when the heat pump is running
ElectricityConsumption_Idle = 5 #W, electricity consumed by the HPWH when idle
NOx_Output = 10 #ng/J, NOx production of the HP when active

#%%---------------CONSTANT DECLARATIONS AND CALCULATIONS-----------------------
#Constants used in water-based calculations
SpecificHeat_Water = 0.998 #Btu/(lb_m-F) @ 80 deg F, http://www.engineeringtoolbox.com/water-properties-d_1508.html
Density_Water = 8.3176 #lb-m/gal @ 80 deg F, http://www.engineeringtoolbox.com/water-density-specific-weight-d_595.html

#Constants used for unit conversions
Hours_In_Day = 24 #The number of hours in a day
Minutes_In_Hour = 60 #The number of minutes in an hour
Seconds_In_Minute = 60 #The number of seconds in a minute
W_To_BtuPerHour = 3.412142 #Converting from Watts to Btu/hr
K_To_F_MagnitudeOnly = 1.8/1. #Converting from K/C to F. Only applicable for magnitudes, not actual temperatures (E.g. Yes for "A temperature difference of 10 C" but not for "The water temperature is 40 C")
Btu_Per_CubicFoot_NaturalGas = 1015 #Energy density of natural gas, in Btu/ft^3
Btu_Per_WattHour = 3.412142 #Conversion factor between Btu nad W-h

#Calculating the NOx production rate of the HPWH when HP is active
NOx_Production_Rate = NOx_Output * FiringRate_HeatPump * Seconds_In_Minute

#Converting quantities from SI units provided by Alex to (Incorrect, silly, obnoxious) IP units
Coefficient_JacketLoss = Coefficient_JacketLoss * W_To_BtuPerHour * K_To_F_MagnitudeOnly #Converts Coefficient_JacketLoss from W/K to Btu/hr-F
Power_Backup = Power_Backup * W_To_BtuPerHour #Btu/hr
FiringRate_HeatPump = FiringRate_HeatPump * W_To_BtuPerHour #Btu/hr

#Calculating the thermal mass of the water in the storage tank
ThermalMass_Tank = Volume_Tank * Density_Water * SpecificHeat_Water

#Reading in the coefficients describing the COP of the gas HPWH as a function of the temperature of the water in the tank
Coefficients_COP = np.fromfile(os.path.dirname(__file__) + os.sep + 'Coefficients\COP_Function_TReturn_F_6Nov2019.csv')

#%%--------------------------MODELING-----------------------------------------

#Creates a 1 dimensional regression stating the COP of the gas heat pump as a function of the temperature of water in the tank
Regression_COP = np.poly1d(Coefficients_COP)

#This section of the code creates a data frame that can be used to represent the simulation model
#The first step is putting the draw profile data into the right format (E.g. If it's CBECC data, we need to convert from event-based to timestep-based)
#The following if-statement takes care of this for 2 different data formats

if Type_DrawProfile == 'CBECC': #Use this code if the draw profile data is from CBECC-Res
#The main challenge with CBECC-Res data is putting the draw profile into a time-step based format, instead of listing out each
#hot water draw event. This code creates a dataframe with 1 minute timesteps and converts the CBECC-Res draw profiles into that
#format
    Draw_Profile = pd.read_csv(Path_DrawProfile) #Create a data frame called Draw_Profile containing the CBECC-Res information
    Number_Days = len(Draw_Profile['Day Of Year (Day)'].unique()) #Identifies the number of days included in the draw profile
    Length_Index_Model = int(Number_Days * Hours_In_Day * Minutes_In_Hour / Timestep) #Identifies the number of minutes included in the draw profile
    Model = pd.DataFrame(index = range(Length_Index_Model)) #Creates a data frame with 1 row for each minute in the draw profile (A model with a 1 minute timestamp)
    Model['Time (min)'] = (Model.index + 1) * Timestep #Create a column in the data frame representing the simulation time
    Model['Hot Water Draw Volume (gal)'] = 0 #Set the default data for hot water draw volume in each time step to 0. This value will later be edited as specific flow volumes for each time step are calculated
    First_Day = Draw_Profile.loc[0, 'Day Of Year (Day)'] #Identifies the day (In interval form, not date form) of the first day of the draw profile
    Draw_Profile['Start Time of Profile (min)'] = Draw_Profile['Start Time of Day (hr)'] * Minutes_In_Hour + (Draw_Profile['Day Of Year (Day)'] - First_Day) * Hours_In_Day * Minutes_In_Hour #Identifies the starting time of each hot water draw in Draw_Profile
    Draw_Profile['End Time of Profile (min)'] = Draw_Profile['Start Time of Day (hr)'] * Minutes_In_Hour + Draw_Profile['Duration (min)'] + (Draw_Profile['Day Of Year (Day)'] - First_Day) * Hours_In_Day * Minutes_In_Hour #Identifies the ending time of each hot water draw in Draw_Profile
    
    for i in Draw_Profile.index: #Iterates through each draw in Draw_Profile
        Start = Draw_Profile.loc[i, 'Start Time of Profile (min)'] #Reads the time when the draw starts
        Bin_Start = int(Start/Timestep) - 1 #Calculates the bin when the draw starts
        End = Draw_Profile.loc[i, 'End Time of Profile (min)'] #Reads the time when the draw ends
        Bin_End = int(End/Timestep) - 1 #Calculates the bin when the draw ends
        Flow_Rate = Draw_Profile.loc[i, 'Hot Water Flow Rate (gal/min)'] #Reads the hot water flow rate of the draw and stores it in the variable Flow_Rate
        Duration = Draw_Profile.loc[i, 'Duration (min)'] #Reads the duration of the draw and stores it in the variable Duration
        Number_Bins = 1 + int(Bin_End) - int(Bin_Start) #Identifies the number of timesteps over which the current draw is performed. E.g. A 10 minute hot water draw starting at 12:02:30 in a profile with 1 minute timeseps would occupy 11 bins (The second half of 12:02, 12:03, 12:04, ..., 12:11, the first half of 12:12)
        
        if Number_Bins == 1: #If the draw only happens during a single timestep
            Model.loc[Bin_Start, 'Hot Water Draw Volume (gal)'] += Flow_Rate * Duration #Add the entire volume of the draw to that timestep
        else: #If it takes place over more than one draw
            Duration_First = Timestep - (Start - Timestep * Bin_Start) #Identify the duration of the draw during the first time step
            Model.loc[Bin_Start, 'Hot Water Draw Volume (gal)'] += Flow_Rate * Duration_First #Set the volume of the draw duing the first time step equal to the flow rate times that duration
            Duration_Last = End - Bin_End * Timestep #Calculate the duration during the final timestep
            Model.loc[Bin_End, 'Hot Water Draw Volume (gal)'] += Flow_Rate * Duration_Last #Set the volume of the draw during the final timestep equal to the flow rate times that duration
            if Number_Bins > 2: #If the draw occurs in more than 2 timesteps (Indicating that there are timesteps with continuous flow between the first and last timestep)
                for i in range(Number_Bins - 2): #For each of the intermediate timesteps
                    Model.loc[Bin_Start, 'Hot Water Draw Volume (gal)'] += Flow_Rate * Timestep #Set the hot water draw volume equal to the flow rate (Times 1 minute)
                    
    Model['Ambient Temperature (deg F)'] = Temperature_Ambient #Sets the ambient temperature in the model equal to the value specified in INPUTS. This value could be replaced with a series of values
    Model['Inlet Water Temperature (deg F)'] = Temperature_Water_Inlet #Sets the inlet temperature in the model equal to the value specified in INPUTS. This value could be replaced with a series of values

elif Type_DrawProfile == 'GTI_Field': #Performs this code if the draw profile data comes from GTI's field study of the gas HPWH
    
    Start_ProfileCreation = time.time()
    
    Draw_Profile = pd.read_csv(Path_DrawProfile, header = 1) #Reads the input data, setting the first row (measurement name) of the .csv file as the header
    Draw_Profile = Draw_Profile.drop([0]) #Deletes the row of the data frame stating the units of each column, as that would cause errors in the calculations
    Draw_Profile = Draw_Profile.reset_index() #Resets the index now that the first row has been removed
    del Draw_Profile['index'] #Deletes the silly little column named 'index' that gets created when resetting hte index
    Model = pd.DataFrame(index = Draw_Profile.index) #Creates a new data frame with the same index as the measured data
    Draw_Profile['ELAPSED TIME'] = Draw_Profile['ELAPSED TIME'].astype(float) #Converts string data to float so the numbers can be used in calculations
    Draw_Profile['Water Flow'] = Draw_Profile['Water Flow'].astype(float) #Converts string data to float so the numbers can be used in calculations
    Draw_Profile['TIME'] = pd.to_datetime(Draw_Profile['TIME']) #Converts string data to time data so the numbers can be used in calculations
    Draw_Profile['Gas Meter'] = Draw_Profile['Gas Meter'].astype(float) #Converts string data to float so the numbers can be used in calculations
    Draw_Profile['Power Draw'] = Draw_Profile['Power Draw'].astype(float) #Converts string data to float so the numbers can be used in calculations
    Draw_Profile['Mid Tank'] = Draw_Profile['Mid Tank'].astype(float) #Converts string data to float so the numbers can be used in calculations
    
    #Model.to_csv(r'C:\Users\jpereira.FE\OneDrive - Frontier Energy, Inc\Desktop\Temp Model Runs\JP Sample\RevisedCBECCDrawProfile.csv', index = False)
   
    values = {'Water Flow': 0} #These two lines set all "nan" entries in Water Flow to 0. This is needed to avoid errors when the data logger resets
    Draw_Profile = Draw_Profile.fillna(value = values)

    if Draw_Profile['ELAPSED TIME'].min() == 0.0: #ELAPSED TIME = 0 when the data logger resets. This code only executes if the data logger reset during the monitoring perio
        Index_Reset = Draw_Profile.loc[Draw_Profile['ELAPSED TIME'] == 0.0].index.item() #Identifies the row in the table when the data logger reset
        for i in range(Index_Reset, len(Draw_Profile.index)): #This for loop updates all entries after the data logger reset with new values, as if the data logger had not resest
            Draw_Profile.loc[i, 'ELAPSED TIME'] = Draw_Profile.loc[i-1, 'ELAPSED TIME'] + (Draw_Profile.loc[i, 'TIME'] - Draw_Profile.loc[i - 1, 'TIME']).seconds #Calculates the actual time since the monitoring data started by adding the time delta to the previous value
            if i == Index_Reset: #Execute this code only for the row that matches the time the datalogger reset
                Delta_Next = Draw_Profile.loc[i + 1, 'Water Flow'] #Identfy the cumulative water flow as of the next entry
                Draw_Profile.loc[i, 'Water Flow'] = Draw_Profile.loc[i-1, 'Water Flow'] #Sets the water flow in this row equal to the water flow in the previous row
            else: #If it's an index other than the one where the dataloffer reset
                Delta = Delta_Next #Update the delta value with the previously recorded delta_next value. This will be used to identify the amount of cumulative water flow as of the end of this timestep
                if i < len(Draw_Profile.index) - 1: #Only do this if it's NOT the last row in the model. Because doing that would cause errors. The computer would overheat, which would ignite the oils on the keyboard from typing, which would burn the air in the office and kill everybody. Then you'd have to file a safety incident report. Sad face :-(
                    Delta_Next = Draw_Profile.loc[i + 1, 'Water Flow'] - Draw_Profile.loc[i, 'Water Flow'] #Identify the increase in cumulative water flow between the current timestep and the next one
                Draw_Profile.loc[i, 'Water Flow'] = Draw_Profile.loc[i - 1, 'Water Flow'] + Delta #Set the cumulative water flow of this timestep equal to the cumulative water flow of the previous timestep + the previously identified delta

    Model['Time (min)'] = (Draw_Profile['ELAPSED TIME'] - Draw_Profile.loc[0, 'ELAPSED TIME'])/60. #Calculate the elapsed time in minutes, instead of seconds, and add it to the 
    Model['Water Flow'] = Draw_Profile['Water Flow'] #Adds a column to Model containing the water flow information from the measured data
    Temperature_Tank_Initial = float(Draw_Profile.loc[0, 'Mid Tank']) #Sets the initial temperature of the modeled tank equal to the initial measured temperature
    Model['Hot Water Draw Volume (gal)'] = 0 #Sets the draw volume during the first timestep in the model to 0. Will be overwritten later if needed
    for i in Draw_Profile.index: #This section calculates the hot water flow during each timestep and adds it to the modeling dataframe
        if i > 0: #This code references the previous timestep, so don't do it on the first timestep. Because that's a terrible idea
            Model.loc[i, 'Hot Water Draw Volume (gal)'] = Draw_Profile.loc[i, 'Water Flow'] - Draw_Profile.loc[i-1, 'Water Flow'] #Find the delta between the cumulative water flow identified in the current and previous timesteps, then enter that value in the current row  
        elif i == 0: #For the very first row
            Model.loc[i, 'Hot Water Draw Volume (gal)'] = 0 #Set it equal to 0. Because there's no previous timestep to calculate from

    Model['Ambient Temperature (deg F)'] = Draw_Profile['Indoor Temp'].astype(float) #Converts data frm string to float so it can be used in calculations
    Model['Inlet Water Temperature (deg F)'] = Draw_Profile['Water In Temp'].astype(float) #Converts data frm string to float so it can be used in calculations

    End_ProfileCreation = time.time()
    
    print('Profile creation time is ' + str(End_ProfileCreation - Start_ProfileCreation))

#The following code simulates the performance of the gas HPWH across different draw profiles
#Initializes a bunch of values at either 0 or initial temperature. They will be overwritten later as needed

Simulation_Start = time.time()

Model['Tank Temperature (deg F)'] = 0
Model.loc[0, 'Tank Temperature (deg F)'] = Temperature_Tank_Initial
Model.loc[1, 'Tank Temperature (deg F)'] = Temperature_Tank_Initial
Model['Jacket Losses (Btu)'] = 0
Model['Energy Withdrawn (Btu)'] = 0
Model['Energy Added Backup (Btu)'] = 0
Model['Energy Added Heat Pump (Btu)'] = 0
Model['Energy Added Total (Btu)'] = 0
Model['COP Gas'] = 0

for i  in range(1, len(Model.index)): #Perform the modeling calculations for each row in the index
       
    Model.loc[i, 'Jacket Losses (Btu)'] = -Coefficient_JacketLoss * (Model.loc[i, 'Tank Temperature (deg F)'] - Model.loc[i, 'Ambient Temperature (deg F)']) * (Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculate the jacket losses through the walls of the tank in Btu
    if Model.loc[i-1, 'Energy Added Backup (Btu)'] == 0: #If the backup heating element was NOT active during the last time step
        Model.loc[i, 'Energy Added Backup (Btu)'] = Power_Backup * int(Model.loc[i, 'Tank Temperature (deg F)'] < Threshold_Activation_Backup) * (Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculate the energy added to the tank using the backup electric resistance elements
    else: #If it WAS active during the last time step
        Model.loc[i, 'Energy Added Backup (Btu)'] = Power_Backup * int(Model.loc[i, 'Tank Temperature (deg F)'] < Threshold_Deactivation_Backup) * (Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculate the energy added to the tank using the backup electric resistance elements
    Model.loc[i, 'Energy Withdrawn (Btu)'] = -Model.loc[i, 'Hot Water Draw Volume (gal)'] * Density_Water * SpecificHeat_Water * (Model.loc[i, 'Tank Temperature (deg F)'] - Model.loc[i, 'Inlet Water Temperature (deg F)']) #Calculate the energy withdrawn by the occupants using hot water
    
    Model.loc[i, 'Energy Added Heat Pump (Btu)'] = FiringRate_HeatPump * Regression_COP(Model.loc[i, 'Tank Temperature (deg F)']) * int(Model.loc[i, 'Tank Temperature (deg F)'] < (Temperature_Tank_Set - Temperature_Tank_Set_Deadband) or Model.loc[i-1, 'Energy Added Heat Pump (Btu)'] > 0 and Model.loc[i, 'Tank Temperature (deg F)'] < Temperature_Tank_Set) * (Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculate the energy added by the heat pump during the previous timestep
        
    Model.loc[i, 'Total Energy Change (Btu)'] = Model.loc[i, 'Jacket Losses (Btu)'] + Model.loc[i, 'Energy Withdrawn (Btu)'] + Model.loc[i, 'Energy Added Backup (Btu)'] + Model.loc[i, 'Energy Added Heat Pump (Btu)'] #Calculate the energy change in the tank during the previous timestep

    #Debugging
#    Model.loc[i, 'Below TSet (-)'] = int(Model.loc[i, 'Tank Temperature (deg F)'] < (Temperature_Tank_Set - Temperature_Tank_Set_Deadband))
#    Model.loc[i, 'Previously On, Still On (-)'] = int(Model.loc[i-1, 'Energy Added Heat Pump (Btu)'] > 0 and Model.loc[i, 'Tank Temperature (deg F)'] < Temperature_Tank_Set)
#    Model.loc[i, 'Heat Pump Control Signal (-)'] = int(Model.loc[i, 'Tank Temperature (deg F)'] < (Temperature_Tank_Set - Temperature_Tank_Set_Deadband) or Model.loc[i-1, 'Energy Added Heat Pump (Btu)'] > 0 and Model.loc[i, 'Tank Temperature (deg F)'] < Temperature_Tank_Set)
    #No longer debugging

    if i < len(Model.index) - 1: #Don't do this for the final timestep. Because that would summon the Knights who Say "Ni"
        Model.loc[i + 1, 'Tank Temperature (deg F)'] = Model.loc[i, 'Total Energy Change (Btu)'] / (ThermalMass_Tank) + Model.loc[i, 'Tank Temperature (deg F)'] #Calculate the tank temperature during the next time step

Model['COP Gas'] = Regression_COP(Model['Tank Temperature (deg F)'])
Model['Elec Energy Demand (Watts)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, ElectricityConsumption_Active, ElectricityConsumption_Idle)
Model['Electric Usage (W-hrs)'] = Model['Elec Energy Demand (Watts)'] * Timestep/60 + (Model['Energy Added Backup (Btu)']/3.413)
Model['Gas Usage (Btu)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Model['Energy Added Heat Pump (Btu)'] / Model['COP Gas'],0)
Model['NOx Production (ng)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Timestep * NOx_Production_Rate, 0)                  
Model['Energy Added Total (Btu)'] = Model['Energy Added Heat Pump (Btu)'] + Model['Energy Added Backup (Btu)'] #Calculate the total energy added to the tank during this timestep
Model['Energy Added Heat Pump (Btu/min)'] = FiringRate_HeatPump * Regression_COP(Model['Tank Temperature (deg F)']) / Minutes_In_Hour * (Model['Energy Added Heat Pump (Btu)'] > 0)

Simulation_End = time.time()

print ('Simulation time is ' + str(Simulation_End - Simulation_Start))

Model.to_csv(os.path.dirname(__file__) + os.sep + 'Output\Output.csv', index = False) #Save the model too the declared file. This should probably be replaced with a dynamic file name for later use in parametric simulations

#%%--------------------------MODEL COMPARISON-----------------------------------------

#This code is only run when comparing the model results to field measurements. It is typically used for model validation
if Compare_To_MeasuredData == 1 and Type_DrawProfile == 'GTI_Field':
    Compare_To_MeasuredData = Model.copy() #Creates a new dataframe specifically for comparing model results to measured data. Starts with the same index and data as the model results, then adds data and calculations from the measured data as necessary

    Compare_To_MeasuredData['Hot Water Draw Volume, Model (gal)'] = Compare_To_MeasuredData['Hot Water Draw Volume (gal)'].cumsum() #Creates a new column in the data frame that cumulatively sums the hot water draw volume in the simulation model. This is then compared to the measured data to ensure that the two are the same
    Compare_To_MeasuredData['Cumulative Hot Water Draw Volume, Data (gal)'] = Draw_Profile['Water Flow'] - Draw_Profile.loc[0, 'Water Flow'] #Creates a new column that represents the cumulative hot water draw volume in the data. The data does not start at 0 gal, so this column subtracts the first value from all values in the column to treat it as if it did start at 0
    Compare_To_MeasuredData['Ambient Temperature, Data (deg F)'] = Draw_Profile['Indoor Temp'] #Creates a new column in the datframe storing the ambient temperature from the measured data
    Compare_To_MeasuredData['Inlet Water Temperature, Data (deg F)'] = Draw_Profile['Water In Temp'] #Creates a new column in the data frame representing the measured inlet water temperature
    Compare_To_MeasuredData['Tank Temperature, Data (deg F)'] = Draw_Profile['Mid Tank'] #Creates a new column in the data frame representing the measured temperature at the middle height of the tank
    Compare_To_MeasuredData['COP, Data'] = Regression_COP(Draw_Profile['Mid Tank']) #Creates a new column in the data frame calculating the COP of the HPWH based on the measured tank water temperature

    Compare_To_MeasuredData['Energy Added, Data (Btu)'] = 0 #Creates a new column for energy added in each timestep with a default value of 0. This value will later be overwritten when the correct value for each timestep is calculated
    Compare_To_MeasuredData['Gas Consumption (Btu)'] = 0 #Creates a new column for gas consumption in each timestep with a default value of 0. This value will later be overwritten when the correct value for each timestep is calculated
    Compare_To_MeasuredData['Energy Added Heat Pump, Model (Btu)'] = Model['Energy Added Heat Pump (Btu)']
    
    for i in range(1, len(Compare_To_MeasuredData)):
        Compare_To_MeasuredData.loc[i, 'Energy Added, Data (Btu)'] = Btu_Per_CubicFoot_NaturalGas * Compare_To_MeasuredData.loc[i, 'COP, Data'] * (Draw_Profile.loc[i, 'Gas Meter'] - Draw_Profile.loc[i-1, 'Gas Meter']) + Btu_Per_WattHour * (Draw_Profile.loc[i, 'Power Draw'] - Draw_Profile.loc[i-1, 'Power Draw']) #Calculates the energy added to the water during each timestep in the measured data
        Compare_To_MeasuredData.loc[i, 'Energy Added Heat Pump, Data (Btu)'] = Btu_Per_CubicFoot_NaturalGas * Compare_To_MeasuredData.loc[i, 'COP, Data'] * (Draw_Profile.loc[i, 'Gas Meter'] - Draw_Profile.loc[i-1, 'Gas Meter']) #Calculates the energy added to the water by the heat pump during each time step in the measured data
        Compare_To_MeasuredData.loc[i, 'Energy Added Heat Pump, Data (Btu/min)'] = Btu_Per_CubicFoot_NaturalGas * Compare_To_MeasuredData.loc[i, 'COP, Data'] * (Draw_Profile.loc[i, 'Gas Meter'] - Draw_Profile.loc[i-1, 'Gas Meter']) / (Compare_To_MeasuredData.loc[i, 'Time (min)'] - Compare_To_MeasuredData.loc[i-1, 'Time (min)']) #Calculates the rate of energy added to the heat pump during each timestep in the measured data
        #Compare_To_MeasuredData.loc[i, 'Energy Added Heat Pump, Model (Btu)'] = FiringRate_HeatPump * Regression_COP(Compare_To_MeasuredData.loc[i, 'Tank Temperature (deg F)']) * int(Compare_To_MeasuredData.loc[i, 'Tank Temperature (deg F)'] < (Temperature_Tank_Set - Temperature_Tank_Set_Deadband) or Compare_To_MeasuredData.loc[i-1, 'Energy Added Heat Pump (Btu)'] > 0 and Compare_To_MeasuredData.loc[i, 'Tank Temperature (deg F)'] < Temperature_Tank_Set) * (Compare_To_MeasuredData.loc[i, 'Time (min)'] - Compare_To_MeasuredData.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculates the energy added by the heat pump during each time step in the model
        #Compare_To_MeasuredData.loc[i, 'Energy Added Heat Pump, Model (Btu/min)'] = FiringRate_HeatPump * Regression_COP(Compare_To_MeasuredData.loc[i, 'Tank Temperature (deg F)']) * int(Compare_To_MeasuredData.loc[i, 'Tank Temperature (deg F)'] < (Temperature_Tank_Set - Temperature_Tank_Set_Deadband) or Compare_To_MeasuredData.loc[i-1, 'Energy Added Heat Pump (Btu)'] > 0 and Compare_To_MeasuredData.loc[i, 'Tank Temperature (deg F)'] < Temperature_Tank_Set) / Minutes_In_Hour #Calculates the rate at which energy is added by the heat pump during each timestep according to the model
        Compare_To_MeasuredData.loc[i, 'Timestep (min)'] = Compare_To_MeasuredData.loc[i, 'Time (min)'] - Compare_To_MeasuredData.loc[i-1, 'Time (min)']
        Model.loc[i, 'Timestep (min)'] = Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']
    
        #Compare_To_MeasuredData['Energy Added Heat Pump, Model (Btu/min)'] = Model['Energy Added Heat Pump (Btu)'] / (Compare_To_MeasuredData.loc[i, 'Time (min)'] - Compare_To_MeasuredData.loc[i-1, 'Time (min)'])
    
    #Generates a series of plots that can be used for comparing the model results to the measured data
        
    tools = [LassoSelectTool(), WheelZoomTool(), BoxZoomTool(), ResetTool()]    
    
    p1 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'Cumulative Hot Water Draw Volume (gal)', tools = tools)
    p1.title.text_font_size = '12pt'
    p1.line(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Hot Water Draw Volume, Model (gal)'], legend = 'Model', color = 'red')
    p1.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Cumulative Hot Water Draw Volume, Data (gal)'], legend = 'Data', color = 'blue')
    
    p2 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'Ambient Temperature (deg F)')
    p2.title.text_font_size = '12pt'
    p2.line(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Ambient Temperature (deg F)'], legend = 'Model', color = 'red')
    p2.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Ambient Temperature, Data (deg F)'], legend = 'Data', color = 'blue') 

    p3 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'Inlet Temperature (deg F)')
    p3.title.text_font_size = '12pt'
    p3.line(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Inlet Water Temperature (deg F)'], legend = 'Model', color = 'red')
    p3.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Inlet Water Temperature, Data (deg F)'], legend = 'Data', color = 'blue') 

    p4 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'Tank Temperature (deg F)')
    p4.title.text_font_size = '12pt'
    p4.line(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Tank Temperature (deg F)'], legend = 'Model', color = 'red')
    p4.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Tank Temperature, Data (deg F)'], legend = 'Data', color = 'blue') 

    p5 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'Energy Added (Btu)')
    p5.title.text_font_size = '12pt'
    p5.line(x = Compare_To_MeasuredData['Time (min)'], y = Model['Energy Added Total (Btu)'], legend = 'Model', color = 'red')
    p5.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Energy Added, Data (Btu)'], legend = 'Data', color = 'blue') 

    p6 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'COP')
    p6.title.text_font_size = '12pt'
    p6.line(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['COP Gas'], legend = 'Model', color = 'red')
    p6.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['COP, Data'], legend = 'Data', color = 'blue') 

    p7 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'Energy Added Heat Pump (Btu)')
    p7.title.text_font_size = '12pt'
    p7.line(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Energy Added Heat Pump, Model (Btu)'], legend = 'Model', color = 'red')
    p7.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Energy Added Heat Pump, Data (Btu)'], legend = 'Data', color = 'blue')

    p8 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'Energy Added Heat Pump (Btu/min)')
    p8.title.text_font_size = '12pt'
    p8.line(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Energy Added Heat Pump (Btu/min)'], legend = 'Model', color = 'red')
    p8.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Energy Added Heat Pump, Data (Btu/min)'], legend = 'Data', color = 'blue')

    p9 = figure(width=1600, height= 400, x_axis_label='Time (min)', y_axis_label = 'Timesteps (min)')
    p9.title.text_font_size = '12pt'
    p9.line(x = Compare_To_MeasuredData['Time (min)'], y = Model['Timestep (min)'], legend = 'Model', color = 'red')
    p9.circle(x = Compare_To_MeasuredData['Time (min)'], y = Compare_To_MeasuredData['Timestep (min)'], legend = 'Data', color = 'blue')
    
    p = gridplot([[p1],[p2], [p3], [p4], [p5], [p6], [p7], [p8], [p9]])
    output_file(os.path.dirname(__file__) + os.sep + 'Validation Data\Validation Plots.html', title = 'Validation Data')
    save(p)
    
    PercentError_Gas = (Compare_To_MeasuredData['Energy Added Total (Btu)'].sum() - Compare_To_MeasuredData['Energy Added Heat Pump, Data (Btu)'].sum()) / Compare_To_MeasuredData['Energy Added, Data (Btu)'].sum() * 100
    PercentError_COP = (Compare_To_MeasuredData['COP Gas'].mean() - Compare_To_MeasuredData['COP, Data'].mean()) / Compare_To_MeasuredData['COP, Data'].mean() * 100
    