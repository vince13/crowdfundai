from locust import HttpUser, task, between, tag
from random import randint, choice
import json

class BaseUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)

    def on_start(self):
        """Login at the start of each user session"""
        self.login()
        self.app_ids = self._get_app_ids()
        self.investment_ids = []
        self.certificate_ids = []

    def login(self):
        """Authenticate user"""
        response = self.client.post("/api/v1/auth/login/", json={
            "email": self.email,
            "password": "testpassword123"
        })
        if response.status_code == 200:
            self.token = response.json()["token"]
            self.client.headers = {'Authorization': f'Bearer {self.token}'}

    def _get_app_ids(self):
        """Get list of available app IDs"""
        response = self.client.get("/api/v1/apps/")
        if response.status_code == 200:
            apps = response.json()["results"]
            return [app["id"] for app in apps]
        return []

class InvestorUser(BaseUser):
    email = "test_investor@example.com"

    @tag('browse')
    @task(5)
    def view_app_listings(self):
        """Browse app listings with different filters"""
        params = choice([
            {},
            {"category": "CHATBOT"},
            {"status": "ACTIVE"},
            {"search": "app"},
            {"sort": "-created_at"}
        ])
        self.client.get("/api/v1/apps/", params=params)

    @tag('browse')
    @task(3)
    def view_app_details(self):
        """View detailed app information"""
        if self.app_ids:
            app_id = choice(self.app_ids)
            self.client.get(f"/api/v1/apps/{app_id}/")

    @tag('investment')
    @task(1)
    def make_investment(self):
        """Make a new investment"""
        if self.app_ids:
            app_id = choice(self.app_ids)
            amount = choice([5000, 10000, 15000, 20000])
            response = self.client.post("/api/v1/investments/", json={
                "app_id": app_id,
                "amount": str(amount),
                "payment_method": "PAYSTACK"
            })
            if response.status_code == 201:
                data = response.json()
                self.investment_ids.append(data["id"])
                self._simulate_payment(data["reference"])

    def _simulate_payment(self, reference):
        """Simulate payment completion"""
        self.client.post("/api/v1/payments/paystack-webhook/", json={
            "event": "charge.success",
            "data": {
                "reference": reference,
                "status": "success",
                "amount": 1000000
            }
        })

    @tag('certificates')
    @task(2)
    def view_certificates(self):
        """View investment certificates"""
        self.client.get("/api/v1/certificates/")
        if self.certificate_ids:
            cert_id = choice(self.certificate_ids)
            self.client.get(f"/api/v1/certificates/{cert_id}/")

    @tag('portfolio')
    @task(2)
    def check_portfolio(self):
        """View investment portfolio"""
        self.client.get("/api/v1/portfolio/")

class DeveloperUser(BaseUser):
    email = "test_developer@example.com"

    @tag('apps')
    @task(3)
    def view_my_apps(self):
        """View developer's apps"""
        self.client.get("/api/v1/developer/apps/")

    @tag('payments')
    @task(2)
    def check_payment_status(self):
        """Check payment status"""
        self.client.get("/api/v1/developer/payment-info/")

    @tag('escrow')
    @task(2)
    def view_escrow_balance(self):
        """Check escrow balance"""
        if self.app_ids:
            app_id = choice(self.app_ids)
            self.client.get(f"/api/v1/developer/escrow/{app_id}/")

class AdminUser(BaseUser):
    email = "test_admin@example.com"

    @tag('admin')
    @task(3)
    def review_apps(self):
        """Review pending apps"""
        self.client.get("/api/v1/admin/apps/pending/")

    @tag('admin')
    @task(2)
    def check_system_metrics(self):
        """Monitor system metrics"""
        self.client.get("/api/v1/admin/metrics/")

    @tag('admin')
    @task(1)
    def verify_certificates(self):
        """Verify generated certificates"""
        self.client.get("/api/v1/admin/certificates/pending/") 