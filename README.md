# Thread-Management-Simulation

![Python](https://img.shields.io/badge/python-3.7%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.0%2B-lightgrey)

A high-performance web server simulation with advanced thread pool management, queue overflow handling, and comprehensive performance monitoring.

## Project Overview

This project simulates a simple web server with sophisticated thread pool management, request queuing, and performance monitoring. It demonstrates:

- Thread pool management with CPU affinity
- Request queue overflow handling
- Comprehensive performance metrics collection
- Real-time monitoring dashboard
- Different endpoint types (fast, medium, slow, upload)
- Bulk request testing capabilities

## Key Features

- **Thread Pool Management**: Configurable thread pool with CPU core affinity
- **Request Queue**: Fixed-size queue with overflow handling and metrics
- **Performance Monitoring**: Comprehensive metrics including:
  - Request throughput
  - Response times
  - Queue length history
  - Thread utilization
  - CPU core assignment
- **Real-time Dashboard**: Matplotlib-based monitoring dashboard
- **Endpoint Simulation**: Various endpoint types with different processing times
- **Bulk Testing**: Special endpoint for stress testing the queue
- **Error Simulation**: Endpoint with configurable error rate

## Project Structure

```
Thread-Management-Simulation/
├── Thread_Simulation.py        # Main server implementation
├── postman_collection_for_bulk_testing.json  # Postman test collection
└── README.md                   # This documentation
```

## Technologies Used

- Python 3.7+
- Flask (Web server framework)
- Threading (Python standard library)
- Matplotlib (Real-time visualization)
- NumPy (Statistical calculations)
- psutil (System monitoring)

## Installation & Setup

1. **Prerequisites**:
   - Python 3.7 or higher
   - pip package manager

2. **Install dependencies**:
   ```bash
   pip install flask matplotlib numpy psutil
   ```

3. **Run the server**:
   ```bash
   python Thread_Simulation.py
   ```

## Usage Guide

### Basic Usage

1. Start the server:
   ```bash
   python Thread_Simulation.py
   ```

2. Access the web interface at `http://localhost:5000`

3. Test different endpoints:
   - `/api/fast` - Fast processing endpoint
   - `/api/medium` - Medium processing endpoint
   - `/api/slow` - Slow processing endpoint
   - `/api/upload` - Upload simulation endpoint (POST)
   - `/api/error` - Error simulation endpoint

### Monitoring Endpoints

- `/api/metrics` - Comprehensive server metrics
- `/api/queue-status` - Real-time queue status

## Performance Dashboard

The real-time monitoring dashboard shows:

1. Thread states (idle/busy)
2. CPU core assignments
3. Queue status and history
4. Dropped requests counter
5. Requests per second
6. Response time distribution
7. System utilization
8. Total processed requests
9. Queue theory visualization
10. Thread state timeline

## Testing

A Postman collection (`postman_collection_for_bulk_testing.json`) is included for comprehensive testing of:

- Queue overflow scenarios
- Bulk request handling
- Error conditions
- Performance metrics collection

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Create a new Pull Request