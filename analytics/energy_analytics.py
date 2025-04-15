import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA
from datetime import datetime, timedelta
import json
import os

class EnergyPatternAnalyzer:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = ['hour', 'day_of_week', 'month', 'temperature', 'humidity']
        
    def preprocess_data(self, historical_data):
        """Preprocess historical energy data for pattern analysis"""
        df = pd.DataFrame(historical_data)
        df['timestamp'] = pd.to_datetime(df['date'])
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        
        # Normalize features
        X = df[self.feature_columns]
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, df['electric_energy'].values
        
    def train_model(self, training_data):
        """Train the pattern analysis model"""
        X, y = self.preprocess_data(training_data)
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X, y)
        
    def predict_pattern(self, input_data):
        """Predict energy consumption pattern"""
        if self.model is None:
            raise ValueError("Model not trained. Call train_model first.")
            
        X = pd.DataFrame([input_data])
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)[0]

class EnergyPredictor:
    def __init__(self):
        self.short_term_model = None
        self.long_term_model = None
        
    def prepare_time_series(self, data):
        """Prepare time series data for prediction"""
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        # Use modern resampling and fill methods
        series = df['electric_energy'].resample('h').mean().ffill()
        return series
        
    def train_short_term(self, data):
        """Train short-term prediction model"""
        try:
            series = self.prepare_time_series(data)
            if len(series) < 24:  # Need at least 24 hours of data
                self.short_term_model = None
                return
                
            # Use simpler model for small datasets
            if len(series) < 100:
                self.short_term_model = ARIMA(series, order=(1,0,0))
            else:
                self.short_term_model = ARIMA(series, order=(1,1,1), seasonal_order=(1,1,1,24))
            self.short_term_model = self.short_term_model.fit()
        except Exception as e:
            print(f"Error training short-term model: {str(e)}")
            self.short_term_model = None
        
    def train_long_term(self, data):
        """Train long-term prediction model"""
        try:
            series = self.prepare_time_series(data)
            if len(series) < 24:  # Need at least 24 hours of data
                self.long_term_model = None
                return
                
            # Use simpler model for small datasets
            if len(series) < 100:
                self.long_term_model = ARIMA(series, order=(1,0,0))
            else:
                self.long_term_model = ARIMA(series, order=(2,1,2), seasonal_order=(1,1,1,24))
            self.long_term_model = self.long_term_model.fit()
        except Exception as e:
            print(f"Error training long-term model: {str(e)}")
            self.long_term_model = None
        
    def predict_next_hour(self):
        """Predict energy usage for the next hour"""
        if self.short_term_model is None:
            return 0.0  # Return 0 if model not trained
        try:
            forecast = self.short_term_model.forecast(steps=1)
            return float(forecast.iloc[0])  # Use iloc for position-based indexing
        except Exception as e:
            print(f"Error in next hour prediction: {str(e)}")
            return 0.0
        
    def predict_next_day(self):
        """Predict energy usage for the next 24 hours"""
        if self.short_term_model is None:
            raise ValueError("Short-term model not trained")
        return self.short_term_model.forecast(steps=24)
        
    def predict_next_week(self):
        """Predict energy usage for the next week"""
        if self.long_term_model is None:
            raise ValueError("Long-term model not trained")
        return self.long_term_model.forecast(steps=168)  # 24 * 7 hours

class CarbonCalculator:
    def __init__(self):
        # Default emission factors (kg CO2/kWh)
        self.emission_factors = {
            'grid': 0.5,
            'solar': 0.0,
            'wind': 0.0,
            'hydro': 0.0,
            'nuclear': 0.0
        }
        
    def update_emission_factors(self, new_factors):
        """Update emission factors with new values"""
        self.emission_factors.update(new_factors)
        
    def calculate_footprint(self, energy_data):
        """Calculate carbon footprint based on energy usage"""
        try:
            total_emissions = 0.0
            for source, amount in energy_data.items():
                if source in self.emission_factors:
                    # Convert amount to float to ensure proper calculation
                    amount = float(amount) if amount is not None else 0.0
                    total_emissions += amount * self.emission_factors[source]
            return total_emissions
        except Exception as e:
            print(f"Error in calculate_footprint: {str(e)}")
            return 0.0
        
    def get_recommendations(self, current_footprint, historical_data):
        """Generate recommendations for reducing carbon footprint"""
        try:
            recommendations = []
            
            # Convert values to float for comparison
            current_footprint = float(current_footprint)
            grid_usage = float(historical_data.get('grid', 0))
            solar_usage = float(historical_data.get('solar', 0))
            
            # Calculate total energy usage
            total_usage = grid_usage + solar_usage
            
            if total_usage > 0:
                solar_percentage = (solar_usage / total_usage) * 100
                
                if solar_percentage < 30:
                    recommendations.append("Consider increasing solar energy usage to reduce carbon footprint.")
                if grid_usage > solar_usage:
                    recommendations.append("Your grid energy usage is higher than solar - try to shift more usage to daylight hours.")
            
            if not recommendations:
                recommendations.append("Maintain your current energy usage pattern while looking for opportunities to increase solar usage.")
                
            return recommendations
        except Exception as e:
            print(f"Error in get_recommendations: {str(e)}")
            return ["Consider increasing solar energy usage to reduce carbon footprint"]

class CostCalculator:
    def __init__(self):
        # Default rate schedule ($/kWh)
        self.rate_schedules = {
            'peak': {
                'hours': [(9, 12), (17, 21)],
                'rate': 0.20
            },
            'off_peak': {
                'hours': [(0, 6)],
                'rate': 0.10
            },
            'shoulder': {
                'hours': [(6, 9), (12, 17), (21, 24)],
                'rate': 0.15
            }
        }
        
    def get_rate_for_time(self, timestamp):
        """Get the applicable rate for a given timestamp"""
        hour = timestamp.hour
        
        for period, schedule in self.rate_schedules.items():
            for start, end in schedule['hours']:
                if start <= hour < end:
                    return schedule['rate']
        return self.rate_schedules['shoulder']['rate']
        
    def calculate_cost(self, consumption_data):
        """Calculate energy costs based on time-of-use pricing"""
        total_cost = 0
        for entry in consumption_data:
            timestamp = pd.to_datetime(entry['date'])
            rate = self.get_rate_for_time(timestamp)
            total_cost += entry['electric_energy'] * rate
        return total_cost
        
    def optimize_schedule(self, consumption_data):
        """Suggest optimal usage times to minimize costs"""
        recommendations = []
        
        # Analyze current usage patterns
        peak_usage = sum(1 for entry in consumption_data 
                        if any(start <= pd.to_datetime(entry['date']).hour < end 
                              for start, end in self.rate_schedules['peak']['hours']))
        
        if peak_usage > len(consumption_data) * 0.3:  # If more than 30% usage during peak
            recommendations.append("Consider shifting some energy usage to off-peak hours to reduce costs.")
            
        return recommendations

class EnergyAnalyticsSystem:
    def __init__(self):
        self.pattern_analyzer = EnergyPatternAnalyzer()
        self.predictor = EnergyPredictor()
        self.carbon_calculator = CarbonCalculator()
        self.cost_calculator = CostCalculator()
        
    def analyze_consumption(self, data):
        """Perform comprehensive energy analysis"""
        try:
            if not data:
                return {
                    'current_pattern': 0.0,
                    'next_hour_prediction': 0.0,
                    'carbon_footprint': 0.0,
                    'energy_cost': 0.0,
                    'recommendations': {
                        'carbon': ["No data available for analysis"],
                        'cost': ["No data available for analysis"]
                    }
                }

            # Convert data for analysis
            current_data = {
                'hour': datetime.now().hour,
                'day_of_week': datetime.now().weekday(),
                'month': datetime.now().month,
                'temperature': float(data[-1].get('temperature', 25)),
                'humidity': float(data[-1].get('humidity', 60))
            }

            # Pattern Analysis
            try:
                self.pattern_analyzer.train_model(data)
                current_pattern = self.pattern_analyzer.predict_pattern(current_data)
            except Exception as e:
                print(f"Pattern analysis error: {str(e)}")
                current_pattern = 0.0

            # Predictions
            try:
                self.predictor.train_short_term(data)
                next_hour = self.predictor.predict_next_hour()
            except Exception as e:
                print(f"Prediction error: {str(e)}")
                next_hour = 0.0

            # Carbon Footprint
            try:
                total_grid_energy = sum(float(entry.get('electric_energy', 0)) for entry in data)
                total_solar_energy = sum(float(entry.get('solar_energy', 0)) for entry in data)
                
                energy_mix = {
                    'grid': total_grid_energy,
                    'solar': total_solar_energy
                }
                
                carbon_footprint = self.carbon_calculator.calculate_footprint(energy_mix)
                carbon_recommendations = self.carbon_calculator.get_recommendations(
                    carbon_footprint,
                    {'solar': total_solar_energy, 'grid': total_grid_energy}
                )
            except Exception as e:
                print(f"Carbon calculation error: {str(e)}")
                carbon_footprint = 0.0
                carbon_recommendations = ["Consider increasing solar energy usage to reduce carbon footprint"]

            # Cost Analysis
            try:
                energy_cost = self.cost_calculator.calculate_cost(data)
                cost_recommendations = self.cost_calculator.optimize_schedule(data)
                if not cost_recommendations:
                    cost_recommendations = ["Consider shifting energy usage to off-peak hours for cost savings"]
            except Exception as e:
                print(f"Cost calculation error: {str(e)}")
                energy_cost = 0.0
                cost_recommendations = ["Try to reduce energy usage during peak hours (9AM-12PM and 5PM-9PM)"]

            return {
                'current_pattern': float(current_pattern),
                'next_hour_prediction': float(next_hour),
                'carbon_footprint': float(carbon_footprint),
                'energy_cost': float(energy_cost),
                'recommendations': {
                    'carbon': carbon_recommendations if carbon_recommendations else ["Consider increasing solar energy usage"],
                    'cost': cost_recommendations if cost_recommendations else ["Shift usage to off-peak hours when possible"]
                }
            }

        except Exception as e:
            print(f"Analysis error: {str(e)}")
            return {
                'current_pattern': 0.0,
                'next_hour_prediction': 0.0,
                'carbon_footprint': 0.0,
                'energy_cost': 0.0,
                'recommendations': {
                    'carbon': ["Error performing analysis"],
                    'cost': ["Error performing analysis"]
                }
            }