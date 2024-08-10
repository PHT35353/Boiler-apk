import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import matplotlib.dates as mdates 

from entsoe import EntsoePandasClient
# required own api token from entsoe
API_TOKEN = '0464a296-1b5d-4be6-a037-b3414de630f8'
client = EntsoePandasClient(api_key=API_TOKEN)

# this function gets the day-ahead and imbalance prices live from entsoe
def entsoe_data(start, end, country_code):

    # putting the start and end time to CET
    start = pd.Timestamp(start, tz='Europe/Brussels')
    end = pd.Timestamp(end, tz='Europe/Brussels')
    
    # getting day-ahead prices
    day_ahead_prices = client.query_day_ahead_prices(country_code, start=start, end=end)
    day_ahead_prices = day_ahead_prices.reset_index()
    day_ahead_prices.columns = ['Time', 'Day-Ahead_Price_EUR_per_MWh']
    
    
    day_ahead_prices['Day-Ahead_Price_EUR_per_MWh'] = day_ahead_prices['Day-Ahead_Price_EUR_per_MWh']
    
    # getting imbalance prices
    imbalance_prices = client.query_imbalance_prices(country_code, start=start, end=end)
    imbalance_prices = imbalance_prices.reset_index()

    # replacing the name of the time column to time and putting a saftey meassure that gives error if such column does not exist
    if 'index' in imbalance_prices.columns:
        imbalance_prices.rename(columns={'index': 'Time'}, inplace=True)
    else:
        st.error("The time column was not found in the imbalance prices data")
        return pd.DataFrame()  
    
    # since there were two columns in the imbalance prices i assigned them accordingly 
    imbalance_prices['Long'] = imbalance_prices['Long']
    imbalance_prices['Short'] = imbalance_prices['Short']
    
    # this combines the two imbalance columns
    if 'Long' in imbalance_prices.columns and 'Short' in imbalance_prices.columns:
        imbalance_prices['Imbalance_Price_EUR_per_MWh'] = imbalance_prices[['Long', 'Short']].mean(axis=1)
    else:
        st.error("The expected two imblance prices columns are not found")
        return pd.DataFrame()  # a saftey meassure that gives this error if the 2 imbalance prices columns are not found
    
    # this only keeps the time and the prices colums of the imbalance data from entsoe
    imbalance_prices = imbalance_prices[['Time', 'Imbalance_Price_EUR_per_MWh']]
    
    # this merges the time column of the day-ahead and imbalance data
    data = pd.merge(day_ahead_prices, imbalance_prices, on='Time', how='outer')
    data['Combined_Price_EUR_per_MWh'] = data[['Day-Ahead_Price_EUR_per_MWh', 'Imbalance_Price_EUR_per_MWh']].mean(axis=1)
    
    return data


# this function checks when is either E-boiler or gas-boiler efficient
def efficient_boiler(combined_price, gas_price):
    if pd.isna(combined_price):
        return 'Unknown'  # if there are no data's it gives unknown
    if combined_price < gas_price / 1000:
        return 'E-boiler'
    else:
        return 'Gas-boiler'

# this function applies the efficient_boiler function to the Combined_Price_EUR_per_MWh column
def calculate_costs(data, gas_price):
    data['Efficient_Boiler'] = data['Combined_Price_EUR_per_MWh'].apply(efficient_boiler, gas_price=gas_price)
    return data

# this function adds the clients desired power as an extra column and it shows the power usage of the efficient boiler only
def calculate_power(data, desired_power):
    data['E-boiler_Power'] = data.apply(lambda x: desired_power if x['Efficient_Boiler'] == 'E-boiler' else 0, axis=1)
    data['Gas-boiler_Power'] = data.apply(lambda x: desired_power if x['Efficient_Boiler'] == 'Gas-boiler' else 0, axis=1)
    return data

# this function calculates the total saving price and precentage
def calculate_savings(data, gas_price, desired_power):
    
    gas_price_per_kwh = gas_price 
    
    # this calculates the total power of each boiler from the desired power in the saved data
    total_e_boiler_power = data['E-boiler_Power'].sum()  # in kW
    total_gas_boiler_power = data['Gas-boiler_Power'].sum()  # in kW
    
    
    total_e_boiler_power_mwh = total_e_boiler_power / 1000  # from kW to MWh
    total_gas_boiler_power_mwh = total_gas_boiler_power / 1000  # from kW to MWh
    
    # calculating the costs per boiler
    e_boiler_cost = total_e_boiler_power_mwh * data[data['Efficient_Boiler'] == 'E-boiler']['Combined_Price_EUR_per_MWh'].mean()
    gas_boiler_cost = total_gas_boiler_power_mwh * gas_price_per_kwh * 1000 
    
    # caclculating the total costs and the saving costs and the saving precentage
    total_cost = gas_boiler_cost - abs(e_boiler_cost)
    total_cost = abs(total_cost)
    total_savings= abs(e_boiler_cost)
    percentage_savings = (total_cost / gas_boiler_cost) * 100 if gas_boiler_cost else 0
    
    return total_savings, percentage_savings, e_boiler_cost, gas_boiler_cost, total_cost


# this function plots the price graph against time
def plot_price(data):
    if 'Time' not in data.columns:
        st.error("No time column error")
        return None # saftey messure that gives this error if there is no time column

    
    data = data.copy()

    # getting the time data
    fig, ax = plt.subplots()
    data['Time'] = pd.to_datetime(data['Time'])
    data.set_index('Time', inplace=True)
    
    # enlarging the graph for better view
    fig, ax = plt.subplots(figsize=(12, 6)) 
    
    # gettingthe boiler data's
    e_boiler_data = data[data['Efficient_Boiler'] == 'E-boiler']
    gas_boiler_data = data[data['Efficient_Boiler'] == 'Gas-boiler']
    
    # plotting the combined prices of day-ahead and imblance and giving E-boiler the calour blue and gas-boiler the colour red. Also some minre size adjustments
    ax.plot(e_boiler_data.index, e_boiler_data['Combined_Price_EUR_per_MWh'], color='blue', label='E-boiler Price', linewidth=0.5, alpha=0.7)
    ax.plot(gas_boiler_data.index, gas_boiler_data['Combined_Price_EUR_per_MWh'], color='red', label='Gas-boiler Price', linewidth=0.5, alpha=0.7 )
    
    ax.set_title('Boiler Price Efficiency Over Time')
    ax.set_xlabel('Time')
    ax.set_ylabel('Price EUR per MWh')
    ax.legend()
    
    # adjusting the angle for better view
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()  # making room for x-axis labels

    return fig


# this function is for plotting the power graph
from scipy.signal import find_peaks

def plot_power(data):
    if 'Time' not in data.columns:
        st.error("No time column error")
        return None # the same saftey meassure as the price graph

    
    data = data.copy()

    # for just giving the peaks (since it is a constant graph) the middle part is not plotted
    data['Time'] = pd.to_datetime(data['Time'])
    data.set_index('Time', inplace=True)
    
    # increasing the size for better view
    fig, ax = plt.subplots(figsize=(14, 8))  

    # this is for adjusting the distance for seeing the peaks more visible and finding the E-boiler and gas-boiler peaks
    e_boiler_peaks, _ = find_peaks(data['E-boiler_Power'], distance=5, prominence=1)  
    gas_boiler_peaks, _ = find_peaks(data['Gas-boiler_Power'], distance=5, prominence=1)

    # finding the zero points of E-boiler and gas-boiler
    e_boiler_zeros = data[data['E-boiler_Power'] == 0].index
    gas_boiler_zeros = data[data['Gas-boiler_Power'] == 0].index

    # plotting only the zeros and the peaks of both e-boiler and gas-boiler
    ax.plot(data.index[e_boiler_peaks], data['E-boiler_Power'].iloc[e_boiler_peaks], 'bo-', label='E-boiler Peaks', markersize=6)
    ax.plot(e_boiler_zeros, data['E-boiler_Power'].loc[e_boiler_zeros], 'b^', label='E-boiler Zeros', markersize=6)
    ax.plot(data.index[gas_boiler_peaks], data['Gas-boiler_Power'].iloc[gas_boiler_peaks], 'ro-', label='Gas-boiler Peaks', markersize=6)
    ax.plot(gas_boiler_zeros, data['Gas-boiler_Power'].loc[gas_boiler_zeros], 'r^', label='Gas-boiler Zeros', markersize=6)

    ax.set_title('Boiler Power Delivery - Peaks and Zeros')
    ax.set_xlabel('Time')
    ax.set_ylabel('Power (kW)')
    ax.legend()

    # adjusting the angle for better view
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()  # making more room for x-axis labels
    return fig





# This function connects everything to streamlit
def main():
    st.title('Boiler Efficiency and Power Analysis')
    
    # showing values in the settings that can be changed by the client
    st.sidebar.title('Settings')
    start_date = st.sidebar.date_input('Start date', pd.to_datetime('2023-01-01'))
    end_date = st.sidebar.date_input('End date', pd.to_datetime('2024-01-01'))
    country_code = st.sidebar.text_input('Country code', 'NL')
    gas_price = st.sidebar.number_input('Gas price per kWh', value=0.30/9.796)
    desired_power = st.sidebar.number_input('Desired Power (kW)', min_value=0.0, value=100.0, step=1.0)
    
    # This function runs everything when the client clicks the get data button
    if st.sidebar.button('Get Data'):
        data = entsoe_data(start_date, end_date, country_code)# gets the data from entsoe
        if data.empty:
            st.error("no data available") # returns error if no data is available
        else:
            
            # calculating the costs and the power from the entered data of the client
            data = calculate_costs(data, gas_price)
            data = calculate_power(data, desired_power)
            
            # shows the data to the client
            st.write('Data Retrieved:')
            st.dataframe(data)
            
            # plots the price and power figures
            price_fig = plot_price(data)
            if price_fig:
                st.pyplot(price_fig)
            
            power_fig = plot_power(data)
            if power_fig:
                st.pyplot(power_fig)
                
            # calls the previous functions and wirtes them
            total_savings, percentage_savings, e_boiler_cost, gas_boiler_cost, total_cost = calculate_savings(data, gas_price, desired_power)
            st.write(f'total Savings: {total_savings:.2f} EUR')
            st.write(f'Percentage Savings: {percentage_savings:.2f}%')
            st.write(f'e_boiler cost: {e_boiler_cost:.2f} EUR')
            st.write(f'gasboiler cost: {gas_boiler_cost:.2f} EUR')
            st.write(f'total cost: {total_cost:.2f} EUR')

if __name__ == '__main__':
    main()


