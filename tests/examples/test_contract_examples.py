"""Example contract tests demonstrating best practices.

This module provides concrete examples of how to write effective contract tests
for different types of service interfaces.
"""

import pytest
from typing import Dict, Any, List
from abc import ABC, abstractmethod


# Example interface definitions
class PaymentProcessorInterface(ABC):
    """Example interface for payment processing services."""
    
    @abstractmethod
    def process_payment(self, amount: float, currency: str, payment_method: str) -> Dict[str, Any]:
        """Process a payment and return result."""
        pass
    
    @abstractmethod
    def refund_payment(self, transaction_id: str, amount: float = None) -> Dict[str, Any]:
        """Process a refund for a transaction."""
        pass
    
    @abstractmethod
    def get_transaction_status(self, transaction_id: str) -> str:
        """Get the status of a transaction."""
        pass


class NotificationServiceInterface(ABC):
    """Example interface for notification services."""
    
    @abstractmethod
    def send_email(self, to: str, subject: str, body: str, **kwargs) -> bool:
        """Send an email notification."""
        pass
    
    @abstractmethod
    def send_sms(self, phone: str, message: str) -> bool:
        """Send an SMS notification."""
        pass
    
    @abstractmethod
    def get_notification_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get notification history for a user."""
        pass


# Mock implementations for testing
class MockPaymentProcessor(PaymentProcessorInterface):
    """Mock payment processor for testing contract compliance."""
    
    def __init__(self):
        self.transactions = {}
        self.next_id = 1
    
    def process_payment(self, amount: float, currency: str, payment_method: str) -> Dict[str, Any]:
        transaction_id = f"txn_{self.next_id}"
        self.next_id += 1
        
        result = {
            'transaction_id': transaction_id,
            'status': 'completed' if amount < 1000 else 'pending',
            'amount': amount,
            'currency': currency,
            'payment_method': payment_method
        }
        
        self.transactions[transaction_id] = result
        return result
    
    def refund_payment(self, transaction_id: str, amount: float = None) -> Dict[str, Any]:
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        original = self.transactions[transaction_id]
        refund_amount = amount or original['amount']
        
        return {
            'refund_id': f"ref_{self.next_id}",
            'original_transaction_id': transaction_id,
            'amount': refund_amount,
            'status': 'completed'
        }
    
    def get_transaction_status(self, transaction_id: str) -> str:
        if transaction_id not in self.transactions:
            return 'not_found'
        return self.transactions[transaction_id]['status']


class MockNotificationService(NotificationServiceInterface):
    """Mock notification service for testing contract compliance."""
    
    def __init__(self):
        self.sent_notifications = []
    
    def send_email(self, to: str, subject: str, body: str, **kwargs) -> bool:
        notification = {
            'type': 'email',
            'to': to,
            'subject': subject,
            'body': body,
            'metadata': kwargs,
            'id': len(self.sent_notifications) + 1
        }
        self.sent_notifications.append(notification)
        return True
    
    def send_sms(self, phone: str, message: str) -> bool:
        notification = {
            'type': 'sms',
            'phone': phone,
            'message': message,
            'id': len(self.sent_notifications) + 1
        }
        self.sent_notifications.append(notification)
        return True
    
    def get_notification_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        # Filter notifications by user_id (simplified logic)
        user_notifications = [n for n in self.sent_notifications 
                            if n.get('to') == user_id or n.get('phone') == user_id]
        return user_notifications[-limit:]


class TestPaymentProcessorContract:
    """Example contract tests for payment processor interface."""
    
    @pytest.fixture
    def payment_processor(self):
        """Provide a payment processor implementation for testing."""
        return MockPaymentProcessor()
    
    def test_process_payment_contract(self, payment_processor):
        """Test that process_payment follows the expected contract."""
        # Test required parameters
        result = payment_processor.process_payment(
            amount=100.0,
            currency='USD',
            payment_method='credit_card'
        )
        
        # Validate return type and structure
        assert isinstance(result, dict), "process_payment must return a dict"
        
        # Validate required fields in response
        required_fields = ['transaction_id', 'status', 'amount', 'currency']
        for field in required_fields:
            assert field in result, f"process_payment result must contain '{field}'"
        
        # Validate field types
        assert isinstance(result['transaction_id'], str), "transaction_id must be a string"
        assert isinstance(result['status'], str), "status must be a string"
        assert isinstance(result['amount'], (int, float)), "amount must be numeric"
        assert isinstance(result['currency'], str), "currency must be a string"
        
        # Validate business logic
        assert result['amount'] == 100.0, "amount in result must match input"
        assert result['currency'] == 'USD', "currency in result must match input"
        assert result['status'] in ['completed', 'pending', 'failed'], "status must be valid"
    
    def test_refund_payment_contract(self, payment_processor):
        """Test that refund_payment follows the expected contract."""
        # First create a transaction to refund
        payment_result = payment_processor.process_payment(50.0, 'USD', 'debit_card')
        transaction_id = payment_result['transaction_id']
        
        # Test full refund
        refund_result = payment_processor.refund_payment(transaction_id)
        
        assert isinstance(refund_result, dict), "refund_payment must return a dict"
        
        required_fields = ['refund_id', 'original_transaction_id', 'amount', 'status']
        for field in required_fields:
            assert field in refund_result, f"refund_payment result must contain '{field}'"
        
        assert refund_result['original_transaction_id'] == transaction_id
        
        # Test partial refund
        partial_refund = payment_processor.refund_payment(transaction_id, 25.0)
        assert partial_refund['amount'] == 25.0
    
    def test_get_transaction_status_contract(self, payment_processor):
        """Test that get_transaction_status follows the expected contract."""
        # Test with valid transaction
        payment_result = payment_processor.process_payment(75.0, 'EUR', 'bank_transfer')
        transaction_id = payment_result['transaction_id']
        
        status = payment_processor.get_transaction_status(transaction_id)
        assert isinstance(status, str), "get_transaction_status must return a string"
        assert status in ['completed', 'pending', 'failed'], "status must be valid"
        
        # Test with invalid transaction
        invalid_status = payment_processor.get_transaction_status('invalid_id')
        assert isinstance(invalid_status, str), "must return string even for invalid ID"
    
    def test_payment_processor_error_handling(self, payment_processor):
        """Test error handling contracts."""
        # Test invalid refund transaction
        with pytest.raises(ValueError):
            payment_processor.refund_payment('nonexistent_transaction')
        
        # Test invalid parameters (if implementation validates)
        # Note: This depends on implementation - contract should specify validation rules


class TestNotificationServiceContract:
    """Example contract tests for notification service interface."""
    
    @pytest.fixture
    def notification_service(self):
        """Provide a notification service implementation for testing."""
        return MockNotificationService()
    
    def test_send_email_contract(self, notification_service):
        """Test that send_email follows the expected contract."""
        result = notification_service.send_email(
            to='test@example.com',
            subject='Test Subject',
            body='Test message body',
            priority='high'
        )
        
        assert isinstance(result, bool), "send_email must return a boolean"
        assert result is True, "send_email should succeed for valid inputs"
    
    def test_send_sms_contract(self, notification_service):
        """Test that send_sms follows the expected contract."""
        result = notification_service.send_sms('+1234567890', 'Test SMS message')
        
        assert isinstance(result, bool), "send_sms must return a boolean"
        assert result is True, "send_sms should succeed for valid inputs"
    
    def test_get_notification_history_contract(self, notification_service):
        """Test that get_notification_history follows the expected contract."""
        # Send some notifications first
        notification_service.send_email('user1@example.com', 'Subject 1', 'Body 1')
        notification_service.send_sms('user1@example.com', 'SMS message')
        
        history = notification_service.get_notification_history('user1@example.com')
        
        assert isinstance(history, list), "get_notification_history must return a list"
        assert len(history) <= 10, "default limit should be 10"
        
        # Test custom limit
        limited_history = notification_service.get_notification_history('user1@example.com', limit=1)
        assert len(limited_history) <= 1, "custom limit should be respected"
        
        # Validate structure of notification objects
        if history:
            notification = history[0]
            assert isinstance(notification, dict), "each notification must be a dict"
            assert 'type' in notification, "notification must have a type"
            assert 'id' in notification, "notification must have an id"


class TestCrossServiceContractExamples:
    """Example cross-service contract tests."""
    
    def test_payment_notification_integration(self):
        """Test that payment and notification services work together."""
        payment_processor = MockPaymentProcessor()
        notification_service = MockNotificationService()
        
        # Process a payment
        payment_result = payment_processor.process_payment(200.0, 'USD', 'credit_card')
        
        # Send notification about payment
        notification_sent = notification_service.send_email(
            to='customer@example.com',
            subject='Payment Confirmation',
            body=f"Your payment of ${payment_result['amount']} has been {payment_result['status']}"
        )
        
        assert notification_sent, "notification should be sent for successful payment"
        
        # Verify notification was recorded
        history = notification_service.get_notification_history('customer@example.com')
        assert len(history) == 1, "notification should appear in history"
        assert 'Payment Confirmation' in history[0]['subject']


class TestContractValidationHelpers:
    """Helper methods and utilities for contract testing."""
    
    @staticmethod
    def validate_response_structure(response: Dict[str, Any], required_fields: List[str], 
                                  field_types: Dict[str, type] = None):
        """Helper to validate response structure compliance."""
        assert isinstance(response, dict), "Response must be a dictionary"
        
        for field in required_fields:
            assert field in response, f"Response must contain field '{field}'"
        
        if field_types:
            for field, expected_type in field_types.items():
                if field in response:
                    assert isinstance(response[field], expected_type), \
                        f"Field '{field}' must be of type {expected_type.__name__}"
    
    @staticmethod
    def validate_error_handling(func, expected_exception, *args, **kwargs):
        """Helper to validate error handling contracts."""
        with pytest.raises(expected_exception):
            func(*args, **kwargs)
    
    def test_validation_helpers(self):
        """Test the validation helper methods."""
        # Test successful validation
        response = {'id': '123', 'status': 'active', 'count': 42}
        required_fields = ['id', 'status']
        field_types = {'id': str, 'status': str, 'count': int}
        
        # Should not raise any exceptions
        self.validate_response_structure(response, required_fields, field_types)
        
        # Test validation failure
        with pytest.raises(AssertionError):
            self.validate_response_structure({}, ['required_field'])
    
    def test_interface_method_coverage(self):
        """Example test to ensure all interface methods are tested."""
        # Get all abstract methods from interface
        payment_methods = [method for method in dir(PaymentProcessorInterface) 
                         if not method.startswith('_') and 
                         hasattr(getattr(PaymentProcessorInterface, method), '__isabstractmethod__')]
        
        # Verify we have tests for all methods
        test_methods = [method for method in dir(TestPaymentProcessorContract) 
                       if method.startswith('test_')]
        
        # Simple check that we have at least one test per interface method
        # In practice, you'd want more sophisticated coverage checking
        assert len(test_methods) >= len(payment_methods), \
            "Should have at least one test method per interface method"