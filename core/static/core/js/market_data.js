class MarketDataClient {
    constructor() {
        this.connect();
        this.callbacks = [];
    }
    
    connect() {
        // Determine WebSocket protocol based on page protocol
        const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        this.socket = new WebSocket(
            wsProtocol + window.location.host + '/ws/market-data/'
        );
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'market_update') {
                this.handleMarketUpdate(data);
            }
        };
        
        this.socket.onclose = () => {
            console.log('Market data connection closed. Reconnecting...');
            setTimeout(() => this.connect(), 5000);
        };
    }
    
    handleMarketUpdate(data) {
        // Notify all registered callbacks
        this.callbacks.forEach(callback => callback(data));
    }
    
    onUpdate(callback) {
        this.callbacks.push(callback);
    }
    
    requestCategory(category) {
        if (this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                category: category
            }));
        }
    }
}

// Initialize market data client
const marketData = new MarketDataClient();
