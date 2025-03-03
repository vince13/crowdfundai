from django.test import TestCase, LiveServerTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Notification, AppListing, Investment
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
from decimal import Decimal
from django.utils import timezone
import time

User = get_user_model()

class NotificationActionsTest(TestCase):
    def setUp(self):
        # Delete any existing test user
        User.objects.filter(username='testuser').delete()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True  # Ensure user is active
        self.user.user_type = 'INVESTOR'  # Set user as investor
        self.user.save()
        
        # Log in the user for API tests
        self.client.login(username='testuser', password='testpass123')
        
        # Create test notifications
        self.notifications = []
        for i in range(3):
            notification = Notification.objects.create(
                user=self.user,
                type=Notification.Type.SYSTEM,
                title=f'Test Notification {i}',
                message=f'Test message {i}',
                severity=Notification.Severity.LOW
            )
            self.notifications.append(notification)

    def test_mark_notification_as_read(self):
        """Test marking a single notification as read"""
        notification = self.notifications[0]
        response = self.client.post(
            reverse('core:mark_notification_read', args=[notification.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_mark_all_notifications_as_read(self):
        """Test marking all notifications as read"""
        response = self.client.post(
            reverse('core:mark_all_read'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        unread_count = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread_count, 0)

    def test_delete_notification(self):
        """Test deleting a single notification"""
        notification = self.notifications[0]
        response = self.client.post(
            reverse('core:delete_notification', args=[notification.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        with self.assertRaises(Notification.DoesNotExist):
            notification.refresh_from_db()

    def test_delete_all_notifications(self):
        """Test deleting all notifications"""
        response = self.client.post(
            reverse('core:delete_all_notifications'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        notification_count = Notification.objects.filter(user=self.user).count()
        self.assertEqual(notification_count, 0)

    def test_get_unread_count(self):
        """Test getting unread notification count"""
        response = self.client.get(
            reverse('core:unread_count'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['count'], 3)

        # Mark one as read
        notification = self.notifications[0]
        notification.is_read = True
        notification.save()

        response = self.client.get(
            reverse('core:unread_count'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        data = json.loads(response.content)
        self.assertEqual(data['count'], 2)

class NotificationUITest(LiveServerTestCase):
    def setUp(self):
        # Delete any existing test user
        User.objects.filter(username='testuser').delete()
        
        # Create and set up user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.user_type = 'INVESTOR'
        self.user.save()
        
        # Create test notifications
        self.notifications = []
        for i in range(3):
            notification = Notification.objects.create(
                user=self.user,
                type=Notification.Type.SYSTEM,
                title=f'Test Notification {i}',
                message=f'Test message {i}',
                severity=Notification.Severity.LOW
            )
            self.notifications.append(notification)
        
        # Create a test app and investment for the dashboard
        self.app = AppListing.objects.create(
            name='Test App',
            description='Test Description',
            ai_features='Test AI Features',
            category=AppListing.Category.OTHER,
            developer=self.user,
            funding_goal=Decimal('10000.00'),
            currency=AppListing.Currency.NGN,
            exchange_rate=Decimal('750.0000'),
            available_percentage=Decimal('20.00'),
            remaining_percentage=Decimal('20.00'),
            price_per_percentage=Decimal('1000.00'),
            equity_percentage=Decimal('100.00'),
            status=AppListing.Status.ACTIVE,
            funding_end_date=timezone.now() + timezone.timedelta(days=30)
        )
        
        self.investment = Investment.objects.create(
            investor=self.user,
            app=self.app,
            amount_paid=Decimal('1000.00'),
            percentage_bought=Decimal('10.00')
        )
        
        # Set up Selenium
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        self.selenium = webdriver.Chrome(options=options)
        self.selenium.implicitly_wait(10)

    def tearDown(self):
        self.selenium.quit()

    def login(self):
        """Log in the test user"""
        try:
            # Navigate to login page
            self.selenium.get(f'{self.live_server_url}/login/')
            
            # Wait for the login form to be present
            username_input = WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.ID, "id_username"))
            )
            password_input = self.selenium.find_element(By.ID, "id_password")
            
            # Fill in the form with the test user credentials
            username_input.send_keys('testuser')
            password_input.send_keys('testpass123')
            
            # Submit the form
            password_input.submit()
            
            # Wait for either dashboard redirect or error message
            WebDriverWait(self.selenium, 10).until(
                lambda driver: (
                    'dashboard' in driver.current_url or  # Success case
                    len(driver.find_elements(By.CLASS_NAME, "alert-danger")) > 0  # Error case
                )
            )
            
            # Check if we got an error message
            error_messages = self.selenium.find_elements(By.CLASS_NAME, "alert-danger")
            if error_messages:
                raise Exception(f"Login failed: {error_messages[0].text}")
                
            # Verify we're on the dashboard
            if 'dashboard' not in self.selenium.current_url:
                raise Exception("Login succeeded but not redirected to dashboard")
                
        except TimeoutException:
            current_url = self.selenium.current_url
            page_source = self.selenium.page_source
            raise Exception(f"Login timeout - Current URL: {current_url}, Page source: {page_source[:500]}")
        except Exception as e:
            raise Exception(f"Login failed: {str(e)}")

    def test_notification_buttons(self):
        """Test notification buttons in the UI"""
        self.login()

        # Go to notifications page
        self.selenium.get(f'{self.live_server_url}/notifications/')

        try:
            # Wait for page to load and verify we have notifications
            notification_list = WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'notification-list'))
            )
            notifications = notification_list.find_elements(By.CLASS_NAME, 'card')
            self.assertEqual(len(notifications), 3)

            # Wait for JavaScript to load
            WebDriverWait(self.selenium, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )

            # Wait for CSRF token to be present
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.NAME, 'csrfmiddlewaretoken'))
            )

            # Get CSRF token and set it in cookie
            csrf_token = self.selenium.find_element(By.NAME, 'csrfmiddlewaretoken').get_attribute('value')
            self.selenium.add_cookie({
                'name': 'csrftoken',
                'value': csrf_token,
                'path': '/'
            })

            # Wait for and test "Mark All as Read" button
            mark_all_btn = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.ID, 'markAllRead'))
            )
            self.selenium.execute_script("arguments[0].click();", mark_all_btn)

            # Wait for AJAX request to complete
            WebDriverWait(self.selenium, 10).until(
                lambda driver: driver.execute_script(
                    'return document.querySelectorAll(".mark-read").length === 0'
                )
            )

            # Test "Delete All" button
            delete_all_btn = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.ID, 'deleteAllNotifications'))
            )
            self.selenium.execute_script("arguments[0].click();", delete_all_btn)

            # Wait for and click confirm button in modal
            confirm_btn = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.ID, 'confirmDeleteAll'))
            )
            
            # Click the confirm button
            self.selenium.execute_script("arguments[0].click();", confirm_btn)

            try:
                # First wait for modal to be hidden
                WebDriverWait(self.selenium, 10).until_not(
                    EC.visibility_of_element_located((By.ID, 'deleteAllModal'))
                )
                
                # Wait for the AJAX request to complete and notifications to be deleted
                start_time = time.time()
                while time.time() - start_time < 10:  # Maximum 10 seconds wait
                    if Notification.objects.filter(user=self.user).count() == 0:
                        break
                    time.sleep(0.5)
                
                # Verify notifications are actually deleted
                self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)
                
                # Manually navigate to notifications page
                self.selenium.get(f'{self.live_server_url}/notifications/')
                
                # Wait for page to load completely
                WebDriverWait(self.selenium, 10).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # Wait for notification list container to be present
                notification_list = WebDriverWait(self.selenium, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'notification-list'))
                )
                
                # Wait for any notification cards to disappear
                WebDriverWait(self.selenium, 10).until(
                    lambda driver: len(notification_list.find_elements(By.CLASS_NAME, 'card')) == 0
                )
                
                # Now check for empty state message
                empty_states = notification_list.find_elements(By.CLASS_NAME, 'alert-info')
                self.assertTrue(len(empty_states) > 0, "Empty state message not found")
                empty_state = empty_states[0]
                self.assertTrue(empty_state.is_displayed())
                self.assertIn("No notifications found", empty_state.text)
                
            except Exception as e:
                # Take screenshot and get page source for debugging
                self.selenium.save_screenshot('test_failure.png')
                page_source = self.selenium.page_source
                self.fail(f"Test failed during alert/reload verification: {str(e)}\nPage source: {page_source[:500]}")

        except Exception as e:
            # Take screenshot and get page source for debugging
            self.selenium.save_screenshot('test_failure.png')
            page_source = self.selenium.page_source
            self.fail(f"Test failed: {str(e)}\nPage source: {page_source[:500]}")

    def test_individual_notification_actions(self):
        """Test individual notification actions in the UI"""
        self.login()

        # Go to notifications page
        self.selenium.get(f'{self.live_server_url}/notifications/')

        try:
            # Wait for page to load and verify we have notifications
            notification_list = WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'notification-list'))
            )
            notifications = notification_list.find_elements(By.CLASS_NAME, 'card')
            self.assertEqual(len(notifications), 3)

            # Wait for JavaScript to load
            WebDriverWait(self.selenium, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )

            # Wait for CSRF token to be present
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.NAME, 'csrfmiddlewaretoken'))
            )

            # Get CSRF token and set it in cookie
            csrf_token = self.selenium.find_element(By.NAME, 'csrfmiddlewaretoken').get_attribute('value')
            self.selenium.add_cookie({
                'name': 'csrftoken',
                'value': csrf_token,
                'path': '/'
            })

            # Test marking individual notification as read
            mark_read_btn = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'mark-read'))
            )
            self.selenium.execute_script("arguments[0].click();", mark_read_btn)

            # Wait for AJAX request to complete
            WebDriverWait(self.selenium, 10).until(
                lambda driver: driver.execute_script(
                    'return document.querySelectorAll(".mark-read").length === 2'
                )
            )

            # Test deleting individual notification
            delete_btn = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'delete-notification'))
            )
            self.selenium.execute_script("arguments[0].click();", delete_btn)

            # Wait for modal to be visible
            WebDriverWait(self.selenium, 10).until(
                EC.visibility_of_element_located((By.ID, 'deleteSingleModal'))
            )

            # Wait for and click confirm button in modal
            confirm_btn = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.ID, 'confirmDeleteSingle'))
            )
            self.selenium.execute_script("arguments[0].click();", confirm_btn)

            # Wait for AJAX request to complete
            WebDriverWait(self.selenium, 10).until(
                lambda driver: driver.execute_script(
                    'return document.querySelectorAll(".card").length === 2'
                )
            )

        except Exception as e:
            # Take screenshot and get page source for debugging
            self.selenium.save_screenshot('test_failure.png')
            page_source = self.selenium.page_source
            self.fail(f"Test failed: {str(e)}\nPage source: {page_source[:500]}") 