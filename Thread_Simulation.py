from flask import Flask, jsonify, request
import threading
import time
import random
import numpy as np
from collections import deque
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from queue import Queue, Empty
import psutil
import os
import uuid

# Metrics for comprehensive monitoring
class ServerMetrics:
    def __init__(self, max_threads=10, queue_size=500):
        # Basic metrics
        self.total_requests = 0
        self.active_requests = 0
        self.response_times = deque(maxlen=100)
        self.request_history = deque(maxlen=60)
        self.start_time = time.time()
        self.lock = threading.Lock()
        
        # Thread pool management
        self.max_threads = max_threads
        self.active_threads = 0
        self.idle_threads = 0
        self.busy_threads = 0
        self.thread_states = deque(maxlen=100)
        
        # Queue management
        self.queue_size = queue_size
        self.request_queue = Queue(maxsize=queue_size)
        self.current_queue_length = 0
        self.queue_history = deque(maxlen=100)
        self.dropped_requests = 0
        self.dropped_history = deque(maxlen=100)
        
        # Response tracking for async requests
        self.pending_responses = {}
        self.completed_responses = {}
        
        # CPU assignment tracking
        self.cpu_assignments = {}
        self.cpu_count = psutil.cpu_count()
        
        # Poisson process parameters
        self.arrival_rate = 2.0
        self.service_rate = 1.5
        
        # Thread pool
        self.worker_threads = []
        self.thread_pool_active = True
        self.initialize_thread_pool()
    
    def initialize_thread_pool(self):
        """Initialize the worker thread pool"""
        for i in range(self.max_threads):
            thread = threading.Thread(target=self.worker_thread, args=(i,))
            thread.daemon = True
            thread.start()
            self.worker_threads.append(thread)
            with self.lock:
                self.idle_threads += 1
    
    def worker_thread(self, thread_id):
        """Worker thread that processes requests from queue"""
        # Assign thread to CPU
        cpu_id = thread_id % self.cpu_count
        self.cpu_assignments[thread_id] = cpu_id
        
        while self.thread_pool_active:
            try:
                # Get request from queue (blocking with timeout)
                request_data = self.request_queue.get(timeout=1.0)
                
                # Mark thread as busy
                with self.lock:
                    self.idle_threads = max(0, self.idle_threads - 1)
                    self.busy_threads += 1
                    self.active_requests += 1
                    self.current_queue_length = self.request_queue.qsize()
                
                # Process the request
                response = self.process_request(request_data, thread_id)
                
                # Store response for later retrieval
                request_id = request_data.get('request_id')
                if request_id:
                    self.completed_responses[request_id] = response
                    # Remove from pending if exists
                    self.pending_responses.pop(request_id, None)
                
                # Mark request as done
                self.request_queue.task_done()
                
                # Mark thread as idle
                with self.lock:
                    self.busy_threads = max(0, self.busy_threads - 1)
                    self.idle_threads += 1
                    self.active_requests = max(0, self.active_requests - 1)
                    self.current_queue_length = self.request_queue.qsize()
                    
            except Empty:
                # No request to process, thread remains idle
                continue
            except Exception as e:
                print(f"Worker thread {thread_id} error: {e}")
                with self.lock:
                    self.busy_threads = max(0, self.busy_threads - 1)
                    self.idle_threads += 1
                    self.active_requests = max(0, self.active_requests - 1)
    
    def process_request(self, request_data, thread_id):
        """Process individual request"""
        start_time = time.time()
        
        # Simulate different processing times based on endpoint
        endpoint_type = request_data.get('type', 'medium')
        if endpoint_type == 'fast':
            processing_time = random.uniform(0.01, 0.05)
        elif endpoint_type == 'medium':
            processing_time = random.uniform(0.1, 0.5)
        elif endpoint_type == 'slow':
            processing_time = random.uniform(0.5, 2.0)
        elif endpoint_type == 'upload':
            processing_time = random.uniform(0.2, 0.8)
        else:
            processing_time = random.uniform(0.1, 0.5)
        
        # Actual processing simulation
        time.sleep(processing_time)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Record metrics
        self.record_request(response_time)
        
        # Return response data
        return {
            'status': 'completed',
            'processing_time': f"{response_time:.3f}s",
            'thread_id': thread_id,
            'endpoint_type': endpoint_type,
            'timestamp': datetime.now().isoformat()
        }
    
    def add_request(self, request_data):
        """Add request to queue or drop if queue is full"""
        try:
            # Try to add to queue (non-blocking)
            self.request_queue.put_nowait(request_data)
            with self.lock:
                self.current_queue_length = self.request_queue.qsize()
                # Update queue history immediately when request is added
                self.queue_history.append(self.current_queue_length)
            return True
        except:
            # Queue is full, drop the request
            with self.lock:
                self.dropped_requests += 1
                self.dropped_history.append(self.dropped_requests)
                print(f"Request dropped! Total dropped: {self.dropped_requests}, Queue size: {self.current_queue_length}")
            return False
    
    def record_request(self, response_time):
        with self.lock:
            self.total_requests += 1
            self.response_times.append(response_time)
            current_second = int(time.time())
            
            # Update request history
            if not self.request_history or self.request_history[-1][0] != current_second:
                self.request_history.append([current_second, 1])
            else:
                self.request_history[-1][1] += 1
            
            # Update thread states history
            self.thread_states.append({
                'timestamp': current_second,
                'idle': self.idle_threads,
                'busy': self.busy_threads,
                'queue_length': self.current_queue_length
            })
    
    def get_cpu_utilization(self):
        """Get current CPU utilization per core"""
        try:
            return psutil.cpu_percent(percpu=True)
        except:
            return [0] * self.cpu_count
    
    def get_queue_statistics(self):
        """Calculate queuing theory statistics"""
        if not self.response_times:
            return {'utilization': 0, 'avg_service_time': 0, 'avg_queue_length': 0, 'throughput': 0}
        
        avg_service_time = np.mean(self.response_times)
        utilization = (self.busy_threads / self.max_threads) if self.max_threads > 0 else 0
        
        # Little's Law: L = λW (average number in system = arrival rate × average time in system)
        avg_queue_length = np.mean(list(self.queue_history)[-10:]) if self.queue_history else 0
        
        return {
            'utilization': utilization,
            'avg_service_time': avg_service_time,
            'avg_queue_length': avg_queue_length,
            'throughput': len(self.response_times) / max(1, time.time() - self.start_time)
        }

# Create Flask app 
app = Flask(__name__)
metrics = ServerMetrics(max_threads=10, queue_size=500)

# Decorator to properly handle queuing
def track_performance_with_queue(endpoint_type='medium'):
    def decorator(f):
        def wrapper(*args, **kwargs):
            # Generate unique request ID
            request_id = str(uuid.uuid4())
            
            # Create request data
            request_data = {
                'type': endpoint_type,
                'timestamp': time.time(),
                'function': f.__name__,
                'request_id': request_id,
                'args': args,
                'kwargs': kwargs
            }
            
            # Try to add to queue
            if metrics.add_request(request_data):
                # Request queued successfully - return immediate response
                with metrics.lock:
                    current_queue_pos = metrics.current_queue_length
                
                return jsonify({
                    'status': 'queued',
                    'message': f'Request queued for {endpoint_type} processing',
                    'request_id': request_id,
                    'queue_position': current_queue_pos,
                    'queue_size': metrics.queue_size,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                # Request dropped due to full queue
                return jsonify({
                    'status': 'dropped',
                    'error': 'Service unavailable - queue full',
                    'dropped_requests': metrics.dropped_requests,
                    'current_queue_length': metrics.current_queue_length,
                    'max_queue_size': metrics.queue_size,
                    'timestamp': datetime.now().isoformat()
                }), 503
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# API Endpoints with queue integration
@app.route('/api/fast', methods=['GET'])
@track_performance_with_queue('fast')
def fast_endpoint():
    """Fast API call - queued processing"""
    return {"message": "Fast processing completed"}

@app.route('/api/medium', methods=['GET', 'POST'])
@track_performance_with_queue('medium')
def medium_endpoint():
    """Medium processing - queued processing"""
    return {"message": "Medium processing completed"}

@app.route('/api/slow', methods=['GET'])
@track_performance_with_queue('slow')
def slow_endpoint():
    """Slow processing - queued processing"""
    return {"message": "Slow processing completed"}

@app.route('/api/upload', methods=['POST'])
@track_performance_with_queue('upload')
def upload_endpoint():
    """File upload - queued processing"""
    return {"message": "Upload processing completed"}

@app.route('/api/error', methods=['GET'])
@track_performance_with_queue('medium')
def error_endpoint():
    """Error simulation - queued processing"""
    if random.random() < 0.3: 
        return {"error": "Simulated error"}, 500
    return {"message": "No error occurred"}

# New endpoint for bulk testing
@app.route('/api/bulk-test', methods=['POST'])
def bulk_test_endpoint():
    """Endpoint specifically for bulk testing to fill the queue quickly"""
    num_requests = request.json.get('count', 100)
    endpoint_type = request.json.get('type', 'medium')
    
    results = {
        'requested': num_requests,
        'queued': 0,
        'dropped': 0,
        'initial_queue_length': metrics.current_queue_length
    }
    
    for i in range(num_requests):
        request_data = {
            'type': endpoint_type,
            'timestamp': time.time(),
            'function': 'bulk_test',
            'request_id': f"bulk_{i}_{uuid.uuid4()}",
            'batch_id': f"bulk_test_{int(time.time())}"
        }
        
        if metrics.add_request(request_data):
            results['queued'] += 1
        else:
            results['dropped'] += 1
    
    results['final_queue_length'] = metrics.current_queue_length
    results['total_dropped'] = metrics.dropped_requests
    
    return jsonify(results)

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get comprehensive server metrics"""
    with metrics.lock:
        uptime = time.time() - metrics.start_time
        avg_response = np.mean(metrics.response_times) if metrics.response_times else 0
        rps = len(metrics.response_times) / min(uptime, 60) if uptime > 0 else 0
        queue_stats = metrics.get_queue_statistics()
        
        return jsonify({
            'total_requests': metrics.total_requests,
            'active_requests': metrics.active_requests,
            'dropped_requests': metrics.dropped_requests,
            'average_response_time': f"{avg_response:.3f}s",
            'requests_per_second': f"{rps:.2f}",
            'uptime_seconds': f"{uptime:.1f}",
            'thread_stats': {
                'max_threads': metrics.max_threads,
                'idle_threads': metrics.idle_threads,
                'busy_threads': metrics.busy_threads,
                'cpu_assignments': metrics.cpu_assignments
            },
            'queue_stats': {
                'current_length': metrics.current_queue_length,
                'max_size': metrics.queue_size,
                'utilization': f"{queue_stats.get('utilization', 0):.2%}",
                'avg_queue_length': f"{queue_stats.get('avg_queue_length', 0):.2f}",
                'queue_full_percentage': f"{(metrics.current_queue_length / metrics.queue_size * 100):.1f}%"
            },
            'cpu_utilization': metrics.get_cpu_utilization(),
            'performance_stats': {
                'throughput': f"{queue_stats.get('throughput', 0):.2f}",
                'avg_service_time': f"{queue_stats.get('avg_service_time', 0):.3f}s"
            }
        })

@app.route('/api/queue-status', methods=['GET'])
def get_queue_status():
    """Get real-time queue status"""
    return jsonify({
        'current_queue_length': metrics.current_queue_length,
        'max_queue_size': metrics.queue_size,
        'queue_utilization': f"{(metrics.current_queue_length / metrics.queue_size * 100):.1f}%",
        'dropped_requests': metrics.dropped_requests,
        'idle_threads': metrics.idle_threads,
        'busy_threads': metrics.busy_threads,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/')
def home():
    """Home page with API documentation"""
    return f'''
    <h1>High-Performance Web Server with Thread Pool Management</h1>
    <h2>Thread Pool Configuration:</h2>
    <ul>
        <li>Max Threads: {metrics.max_threads}</li>
        <li>Queue Size: {metrics.queue_size}</li>
        <li>CPU Cores: {metrics.cpu_count}</li>
        <li>Current Queue Length: <span id="queue-length">{metrics.current_queue_length}</span></li>
        <li>Dropped Requests: <span id="dropped">{metrics.dropped_requests}</span></li>
    </ul>
    <h2>Available Endpoints:</h2>
    <ul>
        <li><a href="/api/fast">/api/fast</a> - Fast response (10-50ms)</li>
        <li><a href="/api/medium">/api/medium</a> - Medium processing (100-500ms)</li>
        <li><a href="/api/slow">/api/slow</a> - Slow processing (500ms-2s)</li>
        <li>/api/upload - POST file upload simulation</li>
        <li>/api/error - Random error simulation</li>
        <li>/api/bulk-test - POST bulk request testing</li>
        <li><a href="/api/metrics">/api/metrics</a> - Comprehensive server metrics</li>
        <li><a href="/api/queue-status">/api/queue-status</a> - Real-time queue status</li>
    </ul>
    <h3>Load Testing Commands:</h3>
    <pre>
# Test queue overflow with Apache Bench:
ab -n 1000 -c 50 http://localhost:5000/api/slow

# Test with bulk endpoint:
curl -X POST http://localhost:5000/api/bulk-test \
  -H "Content-Type: application/json" \
  -d '{{"count": 600, "type": "slow"}}'

# Monitor real-time:
curl http://localhost:5000/api/queue-status
    </pre>
    
    <script>
        // Auto-refresh queue status
        setInterval(function() {{
            fetch('/api/queue-status')
                .then(response => response.json())
                .then(data => {{
                    document.getElementById('queue-length').innerText = data.current_queue_length;
                    document.getElementById('dropped').innerText = data.dropped_requests;
                }});
        }}, 1000);
    </script>
    '''

# Monitoring with proper queue visualization
def start_enhanced_monitoring():
    """Start comprehensive performance monitoring dashboard"""
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle('Web Server Thread Pool & Queue Management Dashboard', fontsize=16, fontweight='bold')
    
    # Create subplots
    gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
    
    # Thread Management (Top Row)
    ax_threads = fig.add_subplot(gs[0, 0])
    ax_cpu = fig.add_subplot(gs[0, 1])
    ax_queue = fig.add_subplot(gs[0, 2])
    ax_dropped = fig.add_subplot(gs[0, 3])
    
    # Performance Metrics (Middle Row)
    ax_rps = fig.add_subplot(gs[1, 0])
    ax_response = fig.add_subplot(gs[1, 1])
    ax_utilization = fig.add_subplot(gs[1, 2])
    ax_total = fig.add_subplot(gs[1, 3])
    
    # Queue Theory & Thread States (Bottom Row)
    ax_queue_theory = fig.add_subplot(gs[2, :2])
    ax_thread_timeline = fig.add_subplot(gs[2, 2:])
    
    def animate_dashboard(frame):
        # Clear all axes
        for ax in [ax_threads, ax_cpu, ax_queue, ax_dropped, ax_rps, 
                  ax_response, ax_utilization, ax_total, ax_queue_theory, ax_thread_timeline]:
            ax.clear()
        
        with metrics.lock:
            current_queue_length = metrics.current_queue_length
            idle_threads = metrics.idle_threads
            busy_threads = metrics.busy_threads
            dropped_requests = metrics.dropped_requests
        
        # 1. Thread Management
        if idle_threads + busy_threads > 0:
            thread_labels = ['Idle', 'Busy']
            thread_counts = [idle_threads, busy_threads]
            colors = ['green', 'red']
            ax_threads.pie(thread_counts, labels=thread_labels, colors=colors, autopct='%1.0f')
        ax_threads.set_title(f'Thread States (Total: {metrics.max_threads})')
        
        # 2. CPU Assignment Visualization
        cpu_data = [0] * metrics.cpu_count
        for thread_id, cpu_id in list(metrics.cpu_assignments.items())[:busy_threads]:
            if cpu_id < len(cpu_data):
                cpu_data[cpu_id] += 1
        
        ax_cpu.bar(range(metrics.cpu_count), cpu_data, color='blue', alpha=0.7)
        ax_cpu.set_title('Threads per CPU Core')
        ax_cpu.set_xlabel('CPU Core')
        ax_cpu.set_ylabel('Active Threads')
        ax_cpu.set_xticks(range(metrics.cpu_count))
        
        # 3. Queue Status
        if current_queue_length > 0 or metrics.queue_size > 0:
            queue_used = current_queue_length
            queue_available = max(0, metrics.queue_size - current_queue_length)
            
            if queue_used > 0 or queue_available > 0:
                queue_data = [queue_used, queue_available]
                queue_labels = [f'Used ({queue_used})', f'Available ({queue_available})']
                queue_colors = ['orange', 'lightgray']
                ax_queue.pie(queue_data, labels=queue_labels, colors=queue_colors, autopct='%1.0f')
        
        ax_queue.set_title(f'Queue Status: {current_queue_length}/{metrics.queue_size}')
        
        # 4. Dropped Requests
        if len(metrics.dropped_history) > 1:
            ax_dropped.plot(list(metrics.dropped_history)[-50:], 'r-', linewidth=2)
        else:
            ax_dropped.text(0.5, 0.5, str(dropped_requests), transform=ax_dropped.transAxes,
                           fontsize=24, ha='center', va='center', fontweight='bold', color='red')
        ax_dropped.set_title(f'Dropped Requests: {dropped_requests}')
        ax_dropped.set_ylabel('Cumulative Dropped')
        ax_dropped.grid(True, alpha=0.3)
        
        # 5. Requests Per Second
        if metrics.request_history:
            recent_rps = [req[1] for req in list(metrics.request_history)[-20:]]
            if recent_rps:
                ax_rps.plot(recent_rps, 'b-', linewidth=2, marker='o')
        ax_rps.set_title('Requests Per Second')
        ax_rps.set_ylabel('RPS')
        ax_rps.grid(True, alpha=0.3)
        
        # 6. Response Times
        if len(metrics.response_times) > 5:
            recent_times = list(metrics.response_times)[-20:]
            ax_response.hist(recent_times, bins=10, color='green', alpha=0.7, edgecolor='black')
            ax_response.set_title('Response Time Distribution')
            ax_response.set_xlabel('Response Time (s)')
            ax_response.set_ylabel('Frequency')
        
        # 7. System Utilization
        queue_stats = metrics.get_queue_statistics()
        utilization = queue_stats.get('utilization', 0)
        
        ax_utilization.bar(['Thread Pool'], [utilization], color='purple', alpha=0.7)
        ax_utilization.set_title('System Utilization')
        ax_utilization.set_ylabel('Utilization %')
        ax_utilization.set_ylim(0, 1)
        ax_utilization.text(0, utilization + 0.05, f'{utilization:.1%}', ha='center')
        
        # 8. Total Requests Counter
        ax_total.text(0.5, 0.5, str(metrics.total_requests), transform=ax_total.transAxes,
                     fontsize=36, ha='center', va='center', fontweight='bold', color='blue')
        ax_total.set_title('Total Processed Requests')
        ax_total.axis('off')
        
        # 9. Queue Theory Visualization
        if len(metrics.queue_history) > 1:
            time_points = range(len(list(metrics.queue_history)[-50:]))
            queue_lengths = list(metrics.queue_history)[-50:]
            
            ax_queue_theory.plot(time_points, queue_lengths, 'orange', linewidth=2, label='Queue Length')
            ax_queue_theory.axhline(y=metrics.queue_size, color='red', linestyle='--', label='Queue Limit')
            ax_queue_theory.fill_between(time_points, queue_lengths, alpha=0.3, color='orange')
            ax_queue_theory.set_title('Queue Length Over Time')
            ax_queue_theory.set_xlabel('Time Points')
            ax_queue_theory.set_ylabel('Queue Length')
            ax_queue_theory.legend()
            ax_queue_theory.grid(True, alpha=0.3)
        
        # 10. Thread State Timeline
        if len(metrics.thread_states) > 1:
            states = list(metrics.thread_states)[-30:]
            time_points = range(len(states))
            idle_counts = [s['idle'] for s in states]
            busy_counts = [s['busy'] for s in states]
            
            ax_thread_timeline.stackplot(time_points, idle_counts, busy_counts,
                                       labels=['Idle Threads', 'Busy Threads'],
                                       colors=['green', 'red'], alpha=0.7)
            ax_thread_timeline.set_title('Thread State Transitions')
            ax_thread_timeline.set_xlabel('Time Points')
            ax_thread_timeline.set_ylabel('Thread Count')
            ax_thread_timeline.legend(loc='upper right')
            ax_thread_timeline.grid(True, alpha=0.3)
    
    # Start animation
    ani = animation.FuncAnimation(fig, animate_dashboard, interval=1000, cache_frame_data=False)
    plt.show(block=True)

def run_flask_server():
    """Run Flask server in separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

def run_server_with_enhanced_monitoring():
    """Run Flask server with comprehensive thread pool monitoring"""
    print("Starting High-Performance Web Server with Thread Pool Management...")
    print("Thread Pool Configuration:")
    print(f"  Max Threads: {metrics.max_threads}")
    print(f"  Queue Size: {metrics.queue_size}")
    print(f"  CPU Cores: {metrics.cpu_count}")
    print("Starting Flask server...")
    
    # Start Flask server in separate thread
    server_thread = threading.Thread(target=run_flask_server)
    server_thread.daemon = True
    server_thread.start()
    
    time.sleep(2)  # Give server time to start
    
    print("Server running on http://localhost:5000")
    print("Starting comprehensive monitoring dashboard...")
    print("\nLoad Testing Commands:")
    print("ab -n 1000 -c 50 http://localhost:5000/api/slow")
    print('curl -X POST http://localhost:5000/api/bulk-test -H "Content-Type: application/json" -d \'{"count": 600, "type": "slow"}\'')
    print("curl http://localhost:5000/api/queue-status")
    print("\nClose the matplotlib window to stop the server.")
    # Run monitoring in main thread (required for matplotlib GUI)
    start_enhanced_monitoring()

if __name__ == '__main__':
    run_server_with_enhanced_monitoring()
