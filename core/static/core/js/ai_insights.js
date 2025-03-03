class AIInsights {
    static async getInsights(appId) {
        try {
            const response = await fetch(`/api/ai/insights/${appId}/`);
            const data = await response.json();
            if (data.status === 'error') {
                console.error('Error:', data.message);
            }
            return data;
        } catch (error) {
            console.error('Error fetching insights:', error);
            return {
                status: 'error',
                data: {
                    risk_score: 5.0,
                    valuation_estimate: 0,
                    market_trend: { trend: 'Neutral', growth_rate: '0%' },
                    growth_potential: { score: 5.0, factors: {} },
                    investment_recommendation: {
                        action: 'Error',
                        confidence_score: 0,
                        key_factors: [],
                        suggested_investment_size: { minimum: 0, recommended: 0 }
                    }
                }
            };
        }
    }

    static async getRiskAnalysis(appId) {
        try {
            const response = await fetch(`/api/ai/risk-analysis/${appId}/`);
            const data = await response.json();
            if (data.status === 'error') {
                throw new Error(data.message);
            }
            return data;
        } catch (error) {
            console.error('Error fetching risk analysis:', error);
            return {
                status: 'error',
                data: {
                    risk_score: 5.0,
                    risk_factors: {
                        development_stage: 'Unknown',
                        team_experience: 5.0,
                        market_competition: 5.0,
                        funding_progress: '0%',
                        technology_maturity: 5.0
                    }
                }
            };
        }
    }

    static async getMarketTrends(appId) {
        try {
            const response = await fetch(`/api/ai/market-trends/${appId}/`);
            const data = await response.json();
            if (data.status === 'error') {
                throw new Error(data.message);
            }
            return data;
        } catch (error) {
            console.error('Error fetching market trends:', error);
            return {
                status: 'error',
                data: {
                    trend: 'Neutral',
                    growth_rate: '0%',
                    market_sentiment: 'Neutral',
                    volatility: 5.0
                }
            };
        }
    }

    static async getGrowthPotential(appId) {
        try {
            const response = await fetch(`/api/ai/growth-potential/${appId}/`);
            const data = await response.json();
            if (data.status === 'error') {
                throw new Error(data.message);
            }
            return data;
        } catch (error) {
            console.error('Error fetching growth potential:', error);
            return {
                status: 'error',
                data: {
                    score: 5.0,
                    factors: {
                        market_opportunity: 5.0,
                        competitive_advantage: 5.0,
                        scalability: 5.0,
                        innovation_level: 5.0,
                        team_capability: 5.0
                    }
                }
            };
        }
    }

    // Helper method to display insights in UI
    static async displayInsights(appId, containerId) {
        const container = document.getElementById(containerId);
        try {
            const insights = await this.getInsights(appId);
            
            // Ensure all required properties exist with fallbacks
            const data = {
                risk_score: insights.data?.risk_score || 5.0,
                valuation_estimate: insights.data?.valuation_estimate || 0,
                investment_recommendation: {
                    action: insights.data?.investment_recommendation?.action || 'Neutral',
                    confidence_score: insights.data?.investment_recommendation?.confidence_score || 0.5
                }
            };

            container.innerHTML = `
                <div class="card">
                    <div class="card-header">
                        <h5>AI Insights</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6>Risk Score</h6>
                                <p class="h3">${data.risk_score}/10</p>
                            </div>
                            <div class="col-md-6">
                                <h6>Valuation Estimate</h6>
                                <p class="h3">$${data.valuation_estimate.toLocaleString()}</p>
                            </div>
                        </div>
                        <div class="mt-4">
                            <h6>Investment Recommendation</h6>
                            <p class="h4">${data.investment_recommendation.action}</p>
                            <p>Confidence: ${(data.investment_recommendation.confidence_score * 100).toFixed(1)}%</p>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            container.innerHTML = `<div class="alert alert-danger">Error loading insights: ${error.message}</div>`;
        }
    }

    static async displayAllInsights(appId) {
        const spinner = document.getElementById('loadingSpinner');
        spinner?.classList.remove('d-none');

        try {
            // Load all insights in parallel with error handling
            const [insights, riskAnalysis, marketTrends, growthPotential] = await Promise.all([
                this.getInsights(appId),
                this.getRiskAnalysis(appId),
                this.getMarketTrends(appId),
                this.getGrowthPotential(appId)
            ]);

            // Update Risk Score with fallback values
            const riskScore = document.getElementById('riskScore');
            if (riskScore) {
                riskScore.innerHTML = `
                    <h2 class="display-4">${insights.data?.risk_score || '5.0'}</h2>
                    <p class="text-muted">Risk Score out of 10</p>
                    <div class="progress">
                        <div class="progress-bar" role="progressbar" 
                             style="width: ${(insights.data?.risk_score || 5) * 10}%" 
                             aria-valuenow="${insights.data?.risk_score || 5}" 
                             aria-valuemin="0" 
                             aria-valuemax="10"></div>
                    </div>
                `;
            }

            // Update other sections similarly with fallback values
            // ... (rest of the display logic)

        } catch (error) {
            console.error('Error loading AI insights:', error);
            document.querySelectorAll('.card-body').forEach(el => {
                el.innerHTML = `<div class="alert alert-danger">Error loading insights</div>`;
            });
        } finally {
            spinner?.classList.add('d-none');
        }
    }
} 