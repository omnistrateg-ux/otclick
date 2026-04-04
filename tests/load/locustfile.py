"""
Load Testing with Locust for Otclick Employer Acquisition Engine.

Usage:
    # Start locust web UI
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    # Headless mode with 100 users, 10 users/second spawn rate, 5 minutes
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
        --users 100 --spawn-rate 10 --run-time 5m --headless

    # With specific scenarios
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
        --tags api --users 50 --spawn-rate 5 --headless
"""

import json
import random
import uuid
from typing import Any

from locust import HttpUser, between, events, tag, task


# Sample data for load testing
SAMPLE_EMPLOYERS = [
    {"name": "Tech Corp", "inn": "7707123456", "website": "https://techcorp.ru"},
    {"name": "Digital Solutions", "inn": "7708234567", "website": "https://digsol.ru"},
    {"name": "IT Services Ltd", "inn": "7709345678", "website": "https://itservices.ru"},
    {"name": "Software House", "inn": "7710456789", "website": "https://swhouse.ru"},
    {"name": "Data Systems", "inn": "7711567890", "website": "https://datasys.ru"},
]

SAMPLE_CAMPAIGNS = [
    {"name": "Q1 Outreach", "template_subject": "Partnership Opportunity"},
    {"name": "Tech Companies", "template_subject": "Tech Solutions Offer"},
    {"name": "Enterprise Sales", "template_subject": "Enterprise Partnership"},
]

LEAD_SOURCES = ["hh.ru", "avito", "superjob", "linkedin", "manual"]
LEAD_STATUSES = ["lead_found", "enrichment_done", "scored", "qualified", "outreach_sent"]


class OtclickAPIUser(HttpUser):
    """
    Simulates typical API user behavior for the Otclick platform.

    Performs a mix of read-heavy and write operations that match
    expected production usage patterns.
    """

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    # Store created resource IDs for subsequent operations
    created_leads: list[str] = []
    created_campaigns: list[str] = []

    def on_start(self):
        """Initialize user session."""
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": "test-load-key",  # Configure in test environment
        }
        # Pre-create some resources for read operations
        self._setup_test_data()

    def _setup_test_data(self):
        """Create initial test data for this user."""
        # Create a campaign for this user
        campaign_data = {
            "name": f"LoadTest Campaign {uuid.uuid4().hex[:8]}",
            "template_subject": "Load Test Subject",
            "template_body": "Load test email body",
        }
        response = self.client.post(
            "/api/v1/campaigns",
            json=campaign_data,
            headers=self.headers,
            name="/api/v1/campaigns [setup]",
        )
        if response.status_code == 201:
            data = response.json()
            self.created_campaigns.append(data.get("id", ""))

    # === Health & Metrics Endpoints ===

    @tag("health")
    @task(10)
    def health_check(self):
        """Check API health - high frequency task."""
        self.client.get("/api/v1/health", name="/api/v1/health")

    @tag("metrics")
    @task(2)
    def get_metrics(self):
        """Fetch Prometheus metrics."""
        self.client.get("/metrics", name="/metrics")

    # === Lead Operations ===

    @tag("api", "leads")
    @task(5)
    def list_leads(self):
        """List leads with pagination - common read operation."""
        params = {
            "page": random.randint(1, 5),
            "size": random.choice([10, 20, 50]),
            "status": random.choice(LEAD_STATUSES + [None]),
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        self.client.get(
            "/api/v1/leads",
            params=params,
            headers=self.headers,
            name="/api/v1/leads",
        )

    @tag("api", "leads")
    @task(3)
    def create_lead(self):
        """Create a new lead."""
        employer = random.choice(SAMPLE_EMPLOYERS)
        lead_data = {
            "employer_name": f"{employer['name']} {uuid.uuid4().hex[:4]}",
            "employer_inn": employer["inn"],
            "source": random.choice(LEAD_SOURCES),
            "source_url": f"https://hh.ru/employer/{random.randint(1000, 9999)}",
            "metadata": {"load_test": True},
        }

        response = self.client.post(
            "/api/v1/leads",
            json=lead_data,
            headers=self.headers,
            name="/api/v1/leads [create]",
        )

        if response.status_code == 201:
            data = response.json()
            lead_id = data.get("id")
            if lead_id:
                self.created_leads.append(lead_id)
                # Keep list manageable
                if len(self.created_leads) > 100:
                    self.created_leads = self.created_leads[-50:]

    @tag("api", "leads")
    @task(4)
    def get_lead_detail(self):
        """Get single lead details."""
        if self.created_leads:
            lead_id = random.choice(self.created_leads)
            self.client.get(
                f"/api/v1/leads/{lead_id}",
                headers=self.headers,
                name="/api/v1/leads/{id}",
            )

    @tag("api", "leads")
    @task(2)
    def transition_lead(self):
        """Transition lead to next status."""
        if self.created_leads:
            lead_id = random.choice(self.created_leads)
            transition_data = {
                "target_status": random.choice(["enrichment_done", "scored", "qualified"]),
                "reason": "Load test transition",
            }
            self.client.post(
                f"/api/v1/leads/{lead_id}/transition",
                json=transition_data,
                headers=self.headers,
                name="/api/v1/leads/{id}/transition",
            )

    @tag("api", "leads")
    @task(2)
    def search_leads(self):
        """Search leads by various criteria."""
        search_params = {
            "q": random.choice(["Tech", "Digital", "IT", "Software", "Data"]),
            "source": random.choice(LEAD_SOURCES),
        }
        self.client.get(
            "/api/v1/leads/search",
            params=search_params,
            headers=self.headers,
            name="/api/v1/leads/search",
        )

    # === Campaign Operations ===

    @tag("api", "campaigns")
    @task(3)
    def list_campaigns(self):
        """List all campaigns."""
        self.client.get(
            "/api/v1/campaigns",
            headers=self.headers,
            name="/api/v1/campaigns",
        )

    @tag("api", "campaigns")
    @task(1)
    def create_campaign(self):
        """Create a new campaign."""
        campaign = random.choice(SAMPLE_CAMPAIGNS)
        campaign_data = {
            "name": f"{campaign['name']} {uuid.uuid4().hex[:6]}",
            "template_subject": campaign["template_subject"],
            "template_body": f"Email body for {campaign['name']}",
            "is_active": True,
        }

        response = self.client.post(
            "/api/v1/campaigns",
            json=campaign_data,
            headers=self.headers,
            name="/api/v1/campaigns [create]",
        )

        if response.status_code == 201:
            data = response.json()
            campaign_id = data.get("id")
            if campaign_id:
                self.created_campaigns.append(campaign_id)
                if len(self.created_campaigns) > 20:
                    self.created_campaigns = self.created_campaigns[-10:]

    @tag("api", "campaigns")
    @task(2)
    def get_campaign_detail(self):
        """Get campaign details."""
        if self.created_campaigns:
            campaign_id = random.choice(self.created_campaigns)
            self.client.get(
                f"/api/v1/campaigns/{campaign_id}",
                headers=self.headers,
                name="/api/v1/campaigns/{id}",
            )

    # === Analytics Operations ===

    @tag("api", "analytics")
    @task(3)
    def get_funnel_metrics(self):
        """Get funnel conversion metrics."""
        params = {
            "period": random.choice(["day", "week", "month"]),
        }
        self.client.get(
            "/api/v1/analytics/funnel",
            params=params,
            headers=self.headers,
            name="/api/v1/analytics/funnel",
        )

    @tag("api", "analytics")
    @task(2)
    def get_dashboard(self):
        """Get dashboard overview."""
        self.client.get(
            "/api/v1/analytics/dashboard",
            headers=self.headers,
            name="/api/v1/analytics/dashboard",
        )

    @tag("api", "analytics")
    @task(1)
    def get_source_stats(self):
        """Get lead source statistics."""
        self.client.get(
            "/api/v1/analytics/sources",
            headers=self.headers,
            name="/api/v1/analytics/sources",
        )

    # === Email Operations ===

    @tag("api", "emails")
    @task(2)
    def list_emails(self):
        """List sent emails."""
        params = {
            "page": 1,
            "size": 20,
        }
        self.client.get(
            "/api/v1/emails",
            params=params,
            headers=self.headers,
            name="/api/v1/emails",
        )

    # === Webhook Operations (simulating external services) ===

    @tag("webhooks")
    @task(1)
    def simulate_email_webhook(self):
        """Simulate email tracking webhook."""
        webhook_data = {
            "event": random.choice(["delivered", "opened", "clicked"]),
            "email_id": str(uuid.uuid4()),
            "timestamp": "2024-01-15T10:00:00Z",
            "metadata": {"ip": "192.168.1.1"},
        }
        self.client.post(
            "/api/v1/webhooks/email-events",
            json=webhook_data,
            headers=self.headers,
            name="/api/v1/webhooks/email-events",
        )


class HeavyReadUser(HttpUser):
    """
    Simulates a heavy read user (dashboards, analytics).

    Represents users who primarily view reports and dashboards.
    """

    wait_time = between(2, 5)

    def on_start(self):
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": "test-load-key",
        }

    @tag("analytics")
    @task(5)
    def get_dashboard(self):
        """Fetch main dashboard."""
        self.client.get(
            "/api/v1/analytics/dashboard",
            headers=self.headers,
            name="/api/v1/analytics/dashboard",
        )

    @tag("analytics")
    @task(3)
    def get_funnel(self):
        """Fetch funnel metrics."""
        self.client.get(
            "/api/v1/analytics/funnel",
            headers=self.headers,
            name="/api/v1/analytics/funnel",
        )

    @tag("leads")
    @task(4)
    def browse_leads(self):
        """Browse through leads."""
        for page in range(1, 4):
            self.client.get(
                "/api/v1/leads",
                params={"page": page, "size": 50},
                headers=self.headers,
                name="/api/v1/leads [browse]",
            )

    @tag("campaigns")
    @task(2)
    def view_campaigns(self):
        """View all campaigns."""
        self.client.get(
            "/api/v1/campaigns",
            headers=self.headers,
            name="/api/v1/campaigns",
        )


class BurstUser(HttpUser):
    """
    Simulates burst traffic patterns (batch operations).

    Represents automated scripts or batch imports.
    """

    wait_time = between(0.1, 0.5)  # Fast operations

    def on_start(self):
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": "test-load-key",
        }

    @tag("burst", "leads")
    @task(1)
    def batch_create_leads(self):
        """Create multiple leads in rapid succession."""
        for i in range(10):
            lead_data = {
                "employer_name": f"Burst Test {uuid.uuid4().hex[:8]}",
                "employer_inn": f"770{random.randint(1000000, 9999999)}",
                "source": "hh.ru",
                "source_url": f"https://hh.ru/employer/{random.randint(1000, 9999)}",
            }
            self.client.post(
                "/api/v1/leads",
                json=lead_data,
                headers=self.headers,
                name="/api/v1/leads [batch]",
            )


# === Event Hooks ===

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("=" * 60)
    print("Starting Otclick Load Test")
    print(f"Target host: {environment.host}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test ends."""
    print("=" * 60)
    print("Load Test Complete")

    # Print summary statistics
    stats = environment.stats
    print(f"\nTotal requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Requests/second: {stats.total.total_rps:.2f}")

    if stats.total.num_failures > 0:
        failure_rate = (stats.total.num_failures / stats.total.num_requests) * 100
        print(f"Failure rate: {failure_rate:.2f}%")

    print("=" * 60)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Track individual requests for detailed analysis."""
    if exception:
        # Log failed requests for debugging
        print(f"FAILED: {request_type} {name} - {exception}")
