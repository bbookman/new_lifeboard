import { render, screen } from '@testing-library/react';
import { DataAvailabilityAlert } from '../DataAvailabilityAlert';

describe('DataAvailabilityAlert', () => {
  test('renders nothing when no messages provided', () => {
    const { container } = render(<DataAvailabilityAlert messages={[]} />);
    expect(container.firstChild).toBeNull();
  });

  test('renders nothing when messages array is undefined', () => {
    const { container } = render(<DataAvailabilityAlert messages={undefined as any} />);
    expect(container.firstChild).toBeNull();
  });

  test('renders alert with single message', () => {
    const messages = ['No data available for limitless at the moment, try again soon'];
    render(<DataAvailabilityAlert messages={messages} />);
    
    expect(screen.getByText('Some data sources are currently unavailable:')).toBeInTheDocument();
    expect(screen.getByText('• No data available for limitless at the moment, try again soon')).toBeInTheDocument();
    expect(screen.getByText('Your summary will be generated with available data sources.')).toBeInTheDocument();
  });

  test('renders alert with multiple messages', () => {
    const messages = [
      'No data available for limitless at the moment, try again soon',
      'No data available for twitter at the moment, try again soon',
      'No data available for news at the moment, try again soon'
    ];
    render(<DataAvailabilityAlert messages={messages} />);
    
    expect(screen.getByText('Some data sources are currently unavailable:')).toBeInTheDocument();
    expect(screen.getByText('• No data available for limitless at the moment, try again soon')).toBeInTheDocument();
    expect(screen.getByText('• No data available for twitter at the moment, try again soon')).toBeInTheDocument();
    expect(screen.getByText('• No data available for news at the moment, try again soon')).toBeInTheDocument();
  });

  test('applies custom className', () => {
    const messages = ['Test message'];
    const { container } = render(<DataAvailabilityAlert messages={messages} className="custom-class" />);
    
    expect(container.firstChild).toHaveClass('custom-class');
  });

  test('has correct styling classes', () => {
    const messages = ['Test message'];
    const { container } = render(<DataAvailabilityAlert messages={messages} />);
    
    expect(container.firstChild).toHaveClass('border-amber-200', 'bg-amber-50');
  });
});