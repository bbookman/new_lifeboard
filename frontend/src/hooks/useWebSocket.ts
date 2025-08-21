import { useEffect, useRef, useCallback, useState } from 'react';

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
  message_id: string;
}

export interface DayUpdateData {
  days_date: string;
  status: string;
  source: string;
  timestamp: string;
  items_count?: number;
}

export interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  onDayUpdate?: (data: DayUpdateData) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  sendMessage: (message: any) => void;
  connect: () => void;
  disconnect: () => void;
  subscribe: (topics: string[]) => void;
  unsubscribe: (topics: string[]) => void;
}

/**
 * Custom hook for WebSocket communication with the Lifeboard backend
 * Handles connection management, message routing, and automatic reconnection
 */
export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const {
    url = 'ws://localhost:8000/ws/processing',
    autoConnect = true,
    onConnect,
    onDisconnect,
    onError,
    onDayUpdate,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const shouldConnectRef = useRef(autoConnect);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(message));
      } catch (error) {
        console.error('[useWebSocket] Error sending message:', error);
      }
    } else {
      console.warn('[useWebSocket] WebSocket not connected, cannot send message');
    }
  }, []);

  const subscribe = useCallback(
    (topics: string[]) => {
      sendMessage({
        type: 'subscription',
        data: { topics },
      });
    },
    [sendMessage],
  );

  const unsubscribe = useCallback(
    (topics: string[]) => {
      sendMessage({
        type: 'unsubscription',
        data: { topics },
      });
    },
    [sendMessage],
  );

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        setLastMessage(message);

        console.log('[useWebSocket] Received message:', message);

        // Handle different message types
        switch (message.type) {
          case 'day_update':
            if (onDayUpdate) {
              onDayUpdate(message.data as DayUpdateData);
            }
            break;

          case 'heartbeat':
            // Respond to heartbeat if it's a ping
            if (message.data?.status === 'ping') {
              sendMessage({
                type: 'heartbeat',
                data: { status: 'pong' },
              });
            }
            break;

          case 'subscription':
            console.log('[useWebSocket] Subscription confirmed:', message.data);
            break;

          case 'error':
            console.error('[useWebSocket] Server error:', message.data);
            break;

          default:
            console.log('[useWebSocket] Unhandled message type:', message.type);
        }
      } catch (error) {
        console.error('[useWebSocket] Error parsing message:', error);
      }
    },
    [onDayUpdate, sendMessage],
  );

  const handleOpen = useCallback(() => {
    console.log('[useWebSocket] Connected to WebSocket');
    setIsConnected(true);
    reconnectCountRef.current = 0;

    // Auto-subscribe to day updates
    setTimeout(() => {
      subscribe(['day_updates', 'processing_updates']);
    }, 100);

    if (onConnect) {
      onConnect();
    }
  }, [onConnect, subscribe]);

  const handleClose = useCallback(
    (event: CloseEvent) => {
      console.log('[useWebSocket] WebSocket closed:', event.code, event.reason);
      setIsConnected(false);
      wsRef.current = null;

      if (onDisconnect) {
        onDisconnect();
      }

      // Attempt reconnection if we should be connected and haven't exceeded attempts
      if (shouldConnectRef.current && reconnectCountRef.current < reconnectAttempts) {
        reconnectCountRef.current += 1;
        console.log(`[useWebSocket] Attempting reconnection ${reconnectCountRef.current}/${reconnectAttempts}`);

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      } else if (reconnectCountRef.current >= reconnectAttempts) {
        console.error('[useWebSocket] Maximum reconnection attempts reached');
      }
    },
    [onDisconnect, reconnectAttempts, reconnectInterval],
  );

  const handleError = useCallback(
    (error: Event) => {
      console.error('[useWebSocket] WebSocket error:', error);

      if (onError) {
        onError(error);
      }
    },
    [onError],
  );

  const connect = useCallback(() => {
    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      console.log('[useWebSocket] Connecting to:', url);
      const ws = new WebSocket(url);

      ws.onopen = handleOpen;
      ws.onmessage = handleMessage;
      ws.onclose = handleClose;
      ws.onerror = handleError;

      wsRef.current = ws;
      shouldConnectRef.current = true;
    } catch (error) {
      console.error('[useWebSocket] Error creating WebSocket connection:', error);
    }
  }, [url, handleOpen, handleMessage, handleClose, handleError]);

  const disconnect = useCallback(() => {
    shouldConnectRef.current = false;

    // Clear reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close WebSocket connection
    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect');
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, []); // Empty dependency array for mount/unmount only

  return {
    isConnected,
    lastMessage,
    sendMessage,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
  };
};
