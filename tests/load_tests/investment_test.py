from locust import HttpUser, task, between, tag
import json
import random

class InvestmentFlowUser(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        """Setup before starting tests"""
        # Login
        response = self.client.post("/api/v1/auth/login/", json={
            "email": "test_investor@example.com",
            "password": "testpassword123"
        })
        if response.status_code == 200:
            self.token = response.json()["token"]
            self.client.headers = {'Authorization': f'Bearer {self.token}'}
            
        # Get available apps
        self.available_apps = self._get_available_apps()
        self.investments = []

    def _get_available_apps(self):
        """Get list of apps available for investment"""
        response = self.client.get("/api/v1/apps/", 
                                 params={"status": "ACTIVE", "has_capacity": "true"})
        if response.status_code == 200:
            return response.json()["results"]
        return []

    @tag('investment_flow')
    @task(1)
    def complete_investment_flow(self):
        """Complete end-to-end investment flow"""
        if not self.available_apps:
            return

        # 1. Select an app
        app = random.choice(self.available_apps)
        
        # 2. View app details
        self.client.get(f"/api/v1/apps/{app['id']}/")
        
        # 3. Get investment options
        response = self.client.get(f"/api/v1/apps/{app['id']}/investment-options/")
        if response.status_code != 200:
            return
            
        # 4. Make investment
        amount = random.choice([5000, 10000, 20000, 50000])
        investment_response = self.client.post("/api/v1/investments/", json={
            "app_id": app['id'],
            "amount": str(amount),
            "payment_method": "PAYSTACK"
        })
        
        if investment_response.status_code != 201:
            return
            
        investment_data = investment_response.json()
        
        # 5. Simulate payment
        self._simulate_payment(investment_data["reference"], amount)
        
        # 6. Verify investment
        self.client.get(f"/api/v1/investments/{investment_data['id']}/")
        
        # 7. Generate certificate
        self.client.post(f"/api/v1/certificates/generate/", json={
            "investment_id": investment_data['id']
        })

    def _simulate_payment(self, reference, amount):
        """Simulate successful payment"""
        self.client.post("/api/v1/payments/paystack-webhook/", json={
            "event": "charge.success",
            "data": {
                "reference": reference,
                "status": "success",
                "amount": amount * 100  # Convert to kobo
            }
        })

    @tag('verification')
    @task(2)
    def verify_investments(self):
        """Verify existing investments"""
        response = self.client.get("/api/v1/investments/")
        if response.status_code == 200:
            investments = response.json()["results"]
            if investments:
                investment = random.choice(investments)
                self.client.get(f"/api/v1/investments/{investment['id']}/")
                self.client.get(f"/api/v1/certificates/{investment['id']}/verify/")

    @tag('portfolio')
    @task(3)
    def check_investment_portfolio(self):
        """Check investment portfolio and performance"""
        self.client.get("/api/v1/portfolio/")
        self.client.get("/api/v1/portfolio/performance/")
        self.client.get("/api/v1/portfolio/analytics/") 