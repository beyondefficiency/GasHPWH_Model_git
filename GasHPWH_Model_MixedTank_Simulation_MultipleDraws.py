# -*- coding: utf-8 -*-
"""
Created on Mon Apr 01 12:53:33 2019

Nathan double-checking Git functionality

This script represents a model of GTI's gas HPWH. It is currently capable of being run using draw profile information from
either CBECC-Res or GTI's field monitoring project. It also currently has two modes, one where it simply predicts the performance
of a device over a given draw profile, and a second where it compares the performance of the device to that which is observed
in the measured data.Right now the model is capable of handling CBECC-Res draw profiles,
generated using our scripts, and data from GTI's field study on these devices.

** Update Nov. 11 2019- this is the simulation version of the script

The model is broken into several different sections. The sections are as follows:
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

"""
TIMING script
Updated: Nov. 13 10 PM
{using much shorter input file}
The names for each code black can be found after the "with CodeTimer(...)" statements...

USING PANDAS FOR THE PRIMARY SIMULATION CALCULATIONS:
Code block 'read from csv' took: 4.75999 ms
Code block 'initial manipulations' took: 6.04542 ms
Code block 'upper nested for loop' took: 139.07914 ms
Code block 'modeling calculations' took: 5433.06770 ms
Code block 'final changes to Model' took: 5.12562 ms
Code block 'write to csv' took: 46.22198 ms
Simulation time is 5.640758991241455

USING NUMPY FOR THE PRIMARY SIMULATION CALCULATIONS:
Code block 'read from csv' took: 3.45724 ms
Code block 'initial manipulations' took: 4.38775 ms
Code block 'upper nested for loop' took: 144.32561 ms
Code block 'modeling calculations' took: 48.67639 ms
Code block 'final changes to Model' took: 5.19892 ms
Code block 'write to csv' took: 38.57653 ms
Simulation time is 0.2520108222961426

- niltis
"""
#%%--------------------------IMPORT STATEMENTS--------------------------------

import pandas as pd
import numpy as np
import os
import sys
import time
import GasHPWH_Model as GasHPWH
from linetimer import CodeTimer

Start_Time = time.time() #begin to time the script

#%%--------------------------USER INPUTS------------------------------------------

#Reading in the coefficients describing the COP of the gas HPWH as a function of the temperature of the water in the tank
Coefficients_COP = np.fromfile(os.path.dirname(__file__) + os.sep + 'Coefficients' + os.sep + 'COP_Function_TReturn_F_6Nov2019.csv')
#Creates a 1 dimensional regression stating the COP of the gas heat pump as a function of the temperature of water in the tank
Regression_COP = np.poly1d(Coefficients_COP)

Temperature_Supply_WaterHeater = 125 #Supply temperature of the water heater, in deg F
Timestep = 5 #Timestep to use in the draw profile and simulation, in minutes
Version = 2019 #States the version of the T24 draw profile data set to use. Currently available options are 2016 and 2019
WeatherSource = 'CA' #Type of weather file to use in the simulation. Currently only supports CA
Water = 'Hot' #specify hot or mixed profile
SDLM = 'Yes' #'Yes or No' dependig on what using
Building_Type = 'Single' #Single or Multi depending on what using
#there are two available base paths to use in the next two lines. uncomment the format you want and use it
# Path_DrawProfile_Base_Path = os.path.dirname(__file__) + os.sep + 'Data' + os.sep + 'Draw_Profiles' + os.sep
Path_DrawProfile_Base_Path = '/Users/nathanieliltis/Dropbox (Beyond Efficiency)/Beyond Efficiency Team Folder/Frontier - Final Absorption HPWH Simulation Scripts/Comparison to Other WHs/Draw Profiles'
Path_DrawProfile_Base_Output_Path = '/Users/nathanieliltis/Dropbox (Beyond Efficiency)/Beyond Efficiency Team Folder/Frontier - Final Absorption HPWH Simulation Scripts/Comparison to Other WHs/Individual Outputs of Simulation Model'
Path_Summary_Output = '/Users/nathanieliltis/Dropbox (Beyond Efficiency)/Beyond Efficiency Team Folder/Frontier - Final Absorption HPWH Simulation Scripts/Comparison to Other WHs'

runs_limit = None # enter None if no limit...if you would like to limit the number of draw profiles the script runs (maybe for testing of the script so it doesnt take to long - enter that here)
vary_inlet_temp = True # enter False to fix inlet water temperature constant, and True to take the inlet water temperature from the draw profile file (to make it vary by climate zone)

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

# #These inputs are a series of constants describing the conditions of the simulation. The constants describing the gas HPWH itself come from communications with Alex of GTI, and may
# #need to be updated if he sends new values
Temperature_Tank_Initial = 115 #Deg F, initial temperature of water in the storage tank. 115 F is the standard set temperature in CBECC
Temperature_Tank_Set = 115 #Deg F, set temperature of the HPWH. 115 F is the standard set temperature in CBECC
Temperature_Tank_Set_Deadband = 15 #Deg F, deadband on the thermostat based on e-mail from Paul Glanville on Oct 31, 2019
Temperature_Water_Inlet = 40 #Deg F, inlet water temperature in this simulation
Temperature_Ambient = 68 #deg F, temperature of the ambient air, placeholder for now
Volume_Tank = 65 #gal, volume of water held in the storage tank
Coefficient_JacketLoss = 2.638 #W/K, Default value from Paul Glanville on Oct 31, 2019
Power_Backup = 1250 #W, electricity consumption of the backup resistance elements
Threshold_Activation_Backup = 95 #Deg F, backup element operates when tank temperature is below this threshold. Note that this operate at the same time as the heat pump
Threshold_Deactivation_Backup = 105 #Deg F, sets the temperature when the backup element disengages after it has been engaged
FiringRate_HeatPump = 2930.72 #W, heat consumed by the heat pump
ElectricityConsumption_Active = 110 #W, electricity consumed by the fan when the heat pump is running
ElectricityConsumption_Idle = 5 #W, electricity consumed by the HPWH when idle
NOx_Output = 10 #ng/J, NOx production of the HP when active

## inputs from first run
# Temperature_Tank_Initial = 135 #Deg F, initial temperature of water in the storage tank
# Temperature_Tank_Set = 135 #Deg F, set temperature of the HPWH
# Temperature_Tank_Set_Deadband = 35 #Deg F, deadband on the thermostat
# Temperature_Water_Inlet = 40 #Deg F, inlet water temperature in this simulation
# Temperature_Ambient = 68 #deg F, temperature of the ambient air, placeholder for now
# Volume_Tank = 73 #gal, volume of water held in the storage tank
# Coefficient_JacketLoss = 5.75 #W/K, based on e-mail from Alex Fridyland on 29 Mar 2019
# Power_Backup = 0 #W, electricity consumption of the backup resistance elements
# Threshold_Activation_Backup = 95 #Deg F, backup element operates when tank temperature is below this threshold. Note that this operate at the same time as the heat pump
# Threshold_Deactivation_Backup = 1t15 #Deg F, sets the temperature when the backup element disengages after it has been engaged
# FiringRate_HeatPump = 2930.72 #W, heat consumed by the heat pump
# ElectricityConsumption_Active = 158.5 #W, electricity consumed by the fan when the heat pump is running
# ElectricityConsumption_Idle = 5 #W, electricity consumed by the HPWH when idle
# NOx_Output = 10 #ng/J, NOx production of the HP when active

#Calculating the NOx production rate of the HPWH when HP is active
NOx_Production_Rate = NOx_Output * FiringRate_HeatPump * Seconds_In_Minute

#Converting quantities from SI units provided by Alex to (Incorrect, silly, obnoxious) IP units
Coefficient_JacketLoss = Coefficient_JacketLoss * W_To_BtuPerHour * K_To_F_MagnitudeOnly #Converts Coefficient_JacketLoss from W/K to Btu/hr-F
Power_Backup = Power_Backup * W_To_BtuPerHour #Btu/hr
FiringRate_HeatPump = FiringRate_HeatPump * W_To_BtuPerHour #Btu/hr

#Calculating the thermal mass of the water in the storage tank
ThermalMass_Tank = Volume_Tank * Density_Water * SpecificHeat_Water

#Stores the parameters describing the HPWH in a list for use in the model
Parameters = [Coefficient_JacketLoss,
                Power_Backup,
                Threshold_Activation_Backup,
                Threshold_Deactivation_Backup,
                FiringRate_HeatPump,
                Temperature_Tank_Set,
                Temperature_Tank_Set_Deadband,
                ThermalMass_Tank,
                ElectricityConsumption_Active,
                ElectricityConsumption_Idle,
                NOx_Production_Rate]

#%%--------------------------DATA STRUCTURES DEPENDENT ON USER INPUTS------------------------------------------

All_Variable_Dicts = {} # a place to store the dictionary of variables for every profile
CZs = [] # a place to store the names of every climate zone used
CFAs = [] # a place to store the names of every conditioned floor area used
for file in os.listdir(Path_DrawProfile_Base_Path): # for every file in the specified base directory
    if file.endswith(".csv"): # if it is a csv file
        split_underscore = file.replace(".csv","").split('_') #the filenames given should be formated such that each pertinent variable is seperated by an underscore. This line is the first step in deriving the variable values for this profile from the profiles name
        this_variable_dict = {each.split("=")[0]: each.split("=")[1] for each in split_underscore} # use a list comprehension to create a dictionary giving the values of each variable and add this dictionary to the list of all dictionaries
        All_Variable_Dicts[file] = this_variable_dict
        if this_variable_dict['CZ'] not in CZs: CZs += [this_variable_dict['CZ']] #add to list of all climate zones run if not already present
        if this_variable_dict['CFA'] not in CFAs: CFAs += [this_variable_dict['CFA']] #add to list of all Conditioned floor areas run if not already present

CZs.sort(key=int)
CFAs.sort(key=int)

for each_dictionary in All_Variable_Dicts:
    if len(All_Variable_Dicts[each_dictionary]) != 8: #if the length is not 7 then the mapping into a dictionary is incorrect and the dictionary should not be used. Bail.
        print("error in the naming of the draw profile files or wrong file used, format should be 'Bldg=[Building Type]_CZ=[Climate Zone]_Wat=[Hot]_Prof=[Profile Number]_SDLM=[Yes/No]_CFA=[Floor Area]_Inc=[Included Draw Types]_Ver=[Source_Data_Year].csv'")
        sys.exit()

kWh_Dataframe = pd.DataFrame(index = CZs, columns = CFAs) #set up a dataframe to store the outputs of each run
Therms_Dataframe = kWh_Dataframe.copy() #set up a dataframe to store the outputs of each run
count = 0

#%%--------------------------MODELING-----------------------------------------

for current_profile in All_Variable_Dicts:
    if runs_limit != None:
        if count >= runs_limit and runs_limit < len(All_Variable_Dicts): #add control to determine how long to run the script.
            print('script stopped early because user limited runs; set runs_limit = None to run all draws')
            sys.exit()
    count += 1
    #The following parameters describe the draw profile(s) being used, taken from the file names provided
    Bedrooms = All_Variable_Dicts[current_profile]['Prof'] #Number of bedrooms used in the simulation
    FloorArea_Conditioned = All_Variable_Dicts[current_profile]['CFA'] #Conditioned floor area of the dwelling used in the simulation
    ClimateZone = All_Variable_Dicts[current_profile]['CZ'] #CA climate zone to use in the simulation
    Include_Code = All_Variable_Dicts[current_profile]['Inc'] #type of draws in the profile used

    with CodeTimer('CFA = {0}, Climate Zone = {1}'.format(FloorArea_Conditioned, ClimateZone)):
        Path_DrawProfile_File_Path = 'Bldg={0}_CZ={1}_Wat={2}_Prof={3}_SDLM={4}_CFA={5}_Inc={6}_Ver={7}.csv'.format(Building_Type,ClimateZone,Water,Bedrooms,SDLM,FloorArea_Conditioned,Include_Code,Version)
        Path_DrawProfile = Path_DrawProfile_Base_Path + os.sep + Path_DrawProfile_File_Path

        #%%--------------------------MODELING-----------------------------------------

        #A dataframe is created, based on the draw profile, in which to run the subsequent simulation
        #The first step is putting the draw profile data into the right format (E.g. If it's CBECC data, we need to convert from event-based to timestep-based)

        #hot water draw event. This code creates a dataframe with 1 minute timesteps and converts the CBECC-Res draw profiles into that
        #format
        # with CodeTimer('read from csv'): #for testing - make sure to indent if using
        Draw_Profile = pd.read_csv(Path_DrawProfile) #Create a data frame called Draw_Profile containing the CBECC-Res information
        # with CodeTimer('initial manipulations'): #for testing - make sure to indent if using
        Draw_Profile['Day of Year (Day)'] = Draw_Profile['Day of Year (Day)'].astype(int) #make sure the days are in integer format, not float, as a sanity check on work below
        Unique_Days = Draw_Profile['Day of Year (Day)'].unique() #Identifies the number of unique days included in the draw profile
        Continuous_Index_Range_of_Days = range(Draw_Profile['Day of Year (Day)'].min(), Draw_Profile['Day of Year (Day)'].max() + 1)
        Missing_Days = [x for x in range(Draw_Profile['Day of Year (Day)'].min(), Draw_Profile['Day of Year (Day)'].max() + 1) if x not in Unique_Days] #identifies the specific days missing
        Length_Index_Model= int(len(Continuous_Index_Range_of_Days) * Hours_In_Day * Minutes_In_Hour / Timestep) #Identifies the number of minutes included in the draw profile
        Model = pd.DataFrame(index = range(Length_Index_Model)) #Creates a data frame with 1 row for each minute in the draw profile (A model with a 1 minute timestamp)
        Model['Time (min)'] = (Model.index + 1) * Timestep #Create a column in the data frame representing the simulation time
        Model['Hot Water Draw Volume (gal)'] = 0 #Set the default data for hot water draw volume in each time step to 0. This value will later be edited as specific flow volumes for each time step are calculated
        Model['Inlet Water Temperature (deg F)'] = 0 #initialize the inlet temperature column
        First_Day = Draw_Profile.loc[0, 'Day of Year (Day)'] #Identifies the day (In integer relative to 365 form, not date form) of the first day of the draw profile
        Draw_Profile['Start Time of Profile (min)'] = Draw_Profile['Start time (hr)'] * Minutes_In_Hour + (Draw_Profile['Day of Year (Day)'] - First_Day) * Hours_In_Day * Minutes_In_Hour #Identifies the starting time of each hot water draw in Draw_Profile relative to first day of draw used
        Draw_Profile['End Time of Profile (min)'] = Draw_Profile['Start time (hr)'] * Minutes_In_Hour + Draw_Profile['Duration (min)'] + (Draw_Profile['Day of Year (Day)'] - First_Day) * Hours_In_Day * Minutes_In_Hour #Identifies the ending time of each hot water draw in Draw_Profile relative to first day of draw used

        # with CodeTimer('upper nested for loop'): #for testing
        for i in Draw_Profile.index: #Iterates through each draw in Draw_Profile
            Start = Draw_Profile.loc[i, 'Start Time of Profile (min)'] #Reads the time when the draw starts
            End = Draw_Profile.loc[i, 'End Time of Profile (min)'] #Reads the time when the draw ends
            Bin_Start = int(np.floor(Start/Timestep) - 1) #Calculates the bin when the draw starts
            Number_Bins = int(np.ceil((End-Start)/Timestep)) #Identifies the number of timesteps over which the current draw is performed. E.g. A 10 minute hot water draw starting at 12:02:30 in a profile with 1 minute timeseps would occupy 11 bins (The second half of 12:02, 12:03, 12:04, ..., 12:11, the first half of 12:12)
            Bin_End = Bin_Start + Number_Bins - 1
            Flow_Rate = Draw_Profile.loc[i, 'Hot Water Flow Rate (gpm)'] #Reads the hot water flow rate of the draw and stores it in the variable Flow_Rate
            Duration = Draw_Profile.loc[i, 'Duration (min)'] #Reads the duration of the draw and stores it in the variable Duration

            if Number_Bins == 1: #If the draw only happens during a single timestep
                Model.loc[Bin_Start, 'Hot Water Draw Volume (gal)'] += Flow_Rate * Duration #Add the entire volume of the draw to that timestep
            else: #If it takes place over more than one draw
                Duration_First = Timestep - (Start - Timestep * (Bin_Start-1)) #Identify the duration of the draw during the first time step
                Model.loc[Bin_Start, 'Hot Water Draw Volume (gal)'] += Flow_Rate * Duration_First #Set the volume of the draw duing the first time step equal to the flow rate times that duration
                Duration_Last = End - (Bin_End-1) * Timestep #Calculate the duration during the final timestep
                Model.loc[Bin_End, 'Hot Water Draw Volume (gal)'] += Flow_Rate * Duration_Last #Set the volume of the draw during the final timestep equal to the flow rate times that duration
                if Number_Bins > 2: #If the draw occurs in more than 2 timesteps (Indicating that there are timesteps with continuous flow between the first and last timestep)
                    for i in range(1,Number_Bins-1): #For each of the intermediate timesteps
                        Model.loc[Bin_Start + i, 'Hot Water Draw Volume (gal)'] += Flow_Rate * Timestep #Set the hot water draw volume equal to the flow rate (Times 1 minute)

            if vary_inlet_temp == True:
                This_Inlet_Temperature = Draw_Profile.loc[i, 'Mains Temperature (deg F)'] #get inlet water temperature from profile
                for i in range(Number_Bins):
                    Model.loc[Bin_Start+i, 'Inlet Water Temperature (deg F)'] = This_Inlet_Temperature

        if vary_inlet_temp == False:
            Model['Inlet Water Temperature (deg F)'] = Temperature_Water_Inlet #Sets the inlet temperature in the model equal to the value specified in INPUTS. This value could be replaced with a series of value
        Model['Ambient Temperature (deg F)'] = Temperature_Ambient #Sets the ambient temperature in the model equal to the value specified in INPUTS. This value could be replaced with a series of values

        # New_Intermitent_Model = Model.copy() #for testing
        # Numpy_Model_This = Model.copy() #for testing
        #The following code simulates the performance of the gas HPWH
        #Initializes a bunch of values at either 0 or initial temperature. They will be overwritten later as needed
        Model['Tank Temperature (deg F)'] = 0
        Model.loc[0, 'Tank Temperature (deg F)'] = Temperature_Tank_Initial
        Model.loc[1, 'Tank Temperature (deg F)'] = Temperature_Tank_Initial
        Model['Jacket Losses (Btu)'] = 0
        Model['Energy Withdrawn (Btu)'] = 0
        Model['Energy Added Backup (Btu)'] = 0
        Model['Energy Added Heat Pump (Btu)'] = 0
        Model['Energy Added Total (Btu)'] = 0
        Model['COP Gas'] = 0
        Model['Total Energy Change (Btu)'] = 0
        Model['Timestep (min)'] = Timestep

        Model = GasHPWH.Model_GasHPWH_MixedTank(Model, Parameters, Regression_COP)

        kWh_Dataframe.loc[ClimateZone,FloorArea_Conditioned] = Model['Electric Usage (W-hrs)'].sum()/1000 #get the annual electricity use of the equipment
        Therms_Dataframe.loc[ClimateZone,FloorArea_Conditioned] = Model['Gas Usage (Btu)'].sum()/100000 #get the annual gas use of the equipment

        #%%--------------------------WRITE RESULTS TO FILE-----------------------------------------
        # with CodeTimer('write to csv'): #for testing
        # Model.to_csv(os.path.dirname(__file__) + os.sep + 'Output' + os.sep + 'Numpy_Output.csv', index = False) #for_testing
        # Model.to_csv(os.path.dirname(__file__) + os.sep + 'Output' + os.sep + 'Output.csv', index = False) #Save the model too the declared file. This should probably be replaced with a dynamic file name for later use in parametric simulations
        Model.to_csv(Path_DrawProfile_Base_Output_Path + os.sep + 'OUTPUT_2_' + current_profile, index = False)

kWh_Dataframe.to_csv(Path_Summary_Output + os.sep + 'kWh_Usage_Summary_2.csv')
Therms_Dataframe.to_csv(Path_Summary_Output + os.sep + 'Therms_Usage_Summary_2.csv')

End_Time = time.time() #begin to time the script
print('script ran{0} draw profiles in {1} seconds'.format(count,(End_Time - Start_Time)))
