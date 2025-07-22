//! Black-Scholes pricing engine for options

use serde::{Deserialize, Serialize};
use std::f64::consts::{E, PI};
use super::types::OptionType;

/// Black-Scholes pricing engine for single-sided options
#[derive(Debug, Clone)]
pub struct BlackScholesPricing {
    /// Current spot price of underlying asset
    pub spot: f64,
    /// Strike price of the option
    pub strike: f64,
    /// Time to expiry in years
    pub time_to_expiry: f64,
    /// Risk-free rate (annual)
    pub risk_free_rate: f64,
    /// Implied volatility (annual)
    pub volatility: f64,
}

impl BlackScholesPricing {
    /// Create a new BlackScholesPricing instance
    pub fn new(spot: f64, strike: f64, time_to_expiry: f64, risk_free_rate: f64, volatility: f64) -> Self {
        Self {
            spot,
            strike,
            time_to_expiry,
            risk_free_rate,
            volatility,
        }
    }

    /// Create with default values for quick initialization
    pub fn default() -> Self {
        Self {
            spot: 50000.0,
            strike: 52000.0,
            time_to_expiry: 7.0 / 365.0,
            risk_free_rate: 0.04,
            volatility: 0.7,
        }
    }

    /// Calculate option premium using Black-Scholes model with transaction costs
    pub fn calculate_premium(&self, option_type: OptionType) -> f64 {
        let base_premium = self.calculate_base_premium(option_type);
        
        // 트랜잭션 비용 추가
        let anchoring_cost = 0.0002; // CREATE + BitVMX 앵커링 비용
        let service_fee = base_premium * 0.03; // 3% 서비스 수수료
        
        base_premium + anchoring_cost + service_fee
    }

    /// Calculate base premium without transaction costs (internal use)
    pub fn calculate_base_premium(&self, option_type: OptionType) -> f64 {
        let d1 = self.calculate_d1();
        let d2 = self.calculate_d2();
        
        match option_type {
            OptionType::Call => {
                self.spot * self.normal_cdf(d1) 
                    - self.strike * E.powf(-self.risk_free_rate * self.time_to_expiry) * self.normal_cdf(d2)
            }
            OptionType::Put => {
                self.strike * E.powf(-self.risk_free_rate * self.time_to_expiry) * self.normal_cdf(-d2)
                    - self.spot * self.normal_cdf(-d1)
            }
        }
    }
    
    /// Calculate Delta (rate of change of option price with respect to underlying price)
    pub fn calculate_delta(&self, option_type: OptionType) -> f64 {
        let d1 = self.calculate_d1();
        
        match option_type {
            OptionType::Call => self.normal_cdf(d1),
            OptionType::Put => self.normal_cdf(d1) - 1.0,
        }
    }
    
    /// Calculate Theta (rate of change of option price with respect to time)
    /// Returns daily theta (divide by 365)
    pub fn calculate_theta(&self, option_type: OptionType) -> f64 {
        let d1 = self.calculate_d1();
        let d2 = self.calculate_d2();
        let sqrt_t = self.time_to_expiry.sqrt();
        
        let common_term = -self.spot * self.normal_pdf(d1) * self.volatility / (2.0 * sqrt_t);
        
        let theta_annual = match option_type {
            OptionType::Call => {
                common_term - self.risk_free_rate * self.strike * E.powf(-self.risk_free_rate * self.time_to_expiry) * self.normal_cdf(d2)
            }
            OptionType::Put => {
                common_term + self.risk_free_rate * self.strike * E.powf(-self.risk_free_rate * self.time_to_expiry) * self.normal_cdf(-d2)
            }
        };
        
        // Return daily theta
        theta_annual / 365.0
    }
    
    /// Calculate implied volatility from market premium (using Newton-Raphson method)
    pub fn implied_volatility_from_premium(&self, market_premium: f64, option_type: OptionType) -> Result<f64, &'static str> {
        let mut vol = 0.3; // Initial guess
        let tolerance = 0.0001;
        let max_iterations = 100;
        
        for _ in 0..max_iterations {
            let mut temp_pricing = self.clone();
            temp_pricing.volatility = vol;
            
            let price = temp_pricing.calculate_premium(option_type);
            let vega = temp_pricing.calculate_vega();
            
            let diff = price - market_premium;
            
            if diff.abs() < tolerance {
                return Ok(vol);
            }
            
            if vega == 0.0 {
                return Err("Vega is zero, cannot continue iteration");
            }
            
            vol -= diff / vega;
            
            // Bound volatility to reasonable range
            if vol < 0.01 {
                vol = 0.01;
            } else if vol > 5.0 {
                vol = 5.0;
            }
        }
        
        Err("Failed to converge")
    }
    
    /// Calculate Vega (sensitivity to volatility)
    pub fn calculate_vega(&self) -> f64 {
        let d1 = self.calculate_d1();
        self.spot * self.normal_pdf(d1) * self.time_to_expiry.sqrt() / 100.0
    }
    
    /// Adjust volatility to achieve target theta
    pub fn adjust_volatility_for_target_theta(&mut self, target_theta: f64, option_type: OptionType) -> Result<f64, &'static str> {
        let tolerance = 0.0001;
        let max_iterations = 100;
        
        for _ in 0..max_iterations {
            let current_theta = self.calculate_theta(option_type);
            let diff = current_theta - target_theta;
            
            if diff.abs() < tolerance {
                return Ok(self.volatility);
            }
            
            // Approximate adjustment using numerical differentiation
            let epsilon = 0.001;
            self.volatility += epsilon;
            let theta_plus = self.calculate_theta(option_type);
            self.volatility -= epsilon;
            
            let theta_sensitivity = (theta_plus - current_theta) / epsilon;
            
            if theta_sensitivity.abs() < 0.00001 {
                return Err("Theta sensitivity too low");
            }
            
            self.volatility -= diff / theta_sensitivity;
            
            // Bound volatility
            if self.volatility < 0.01 {
                self.volatility = 0.01;
            } else if self.volatility > 2.0 {
                self.volatility = 2.0;
            }
        }
        
        Err("Failed to converge to target theta")
    }
    
    // Helper functions
    fn calculate_d1(&self) -> f64 {
        ((self.spot / self.strike).ln() + (self.risk_free_rate + self.volatility.powi(2) / 2.0) * self.time_to_expiry)
            / (self.volatility * self.time_to_expiry.sqrt())
    }
    
    fn calculate_d2(&self) -> f64 {
        self.calculate_d1() - self.volatility * self.time_to_expiry.sqrt()
    }
    
    /// Normal cumulative distribution function
    fn normal_cdf(&self, x: f64) -> f64 {
        0.5 * (1.0 + self.erf(x / 2.0_f64.sqrt()))
    }
    
    /// Normal probability density function
    fn normal_pdf(&self, x: f64) -> f64 {
        (1.0 / (2.0 * PI).sqrt()) * E.powf(-0.5 * x.powi(2))
    }
    
    /// Error function approximation
    fn erf(&self, x: f64) -> f64 {
        let a1 =  0.254829592;
        let a2 = -0.284496736;
        let a3 =  1.421413741;
        let a4 = -1.453152027;
        let a5 =  1.061405429;
        let p  =  0.3275911;
        
        let sign = if x < 0.0 { -1.0 } else { 1.0 };
        let x = x.abs();
        
        let t = 1.0 / (1.0 + p * x);
        let y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * E.powf(-x * x);
        
        sign * y
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_black_scholes_call_premium() {
        let bs = BlackScholesPricing {
            spot: 50000.0,
            strike: 52000.0,
            time_to_expiry: 7.0 / 365.0, // 7 days
            risk_free_rate: 0.05,
            volatility: 0.7,
        };
        
        let premium = bs.calculate_premium(OptionType::Call);
        assert!(premium > 0.0);
        assert!(premium < bs.spot); // Premium should be less than spot
    }
    
    #[test]
    fn test_theta_calculation() {
        let bs = BlackScholesPricing {
            spot: 50000.0,
            strike: 52000.0,
            time_to_expiry: 7.0 / 365.0,
            risk_free_rate: 0.05,
            volatility: 0.7,
        };
        
        let theta = bs.calculate_theta(OptionType::Call);
        assert!(theta < 0.0); // Theta should be negative (time decay)
    }
}