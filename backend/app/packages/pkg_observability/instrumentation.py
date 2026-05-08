import logging
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI
from fastapi.responses import Response

# 1. Provide Tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# In production this points to JaegerExporter or OTLPSpanExporter
# We've disabled Console for local docker-compose as it floods logs.
# span_processor = BatchSpanProcessor(ConsoleSpanExporter())
# trace.get_tracer_provider().add_span_processor(span_processor)

# 2. Provide Metrics
REQUEST_COUNT = Counter("api_requests_total", "Total API Requests", ["method", "endpoint", "http_status"])
REQUEST_LATENCY = Histogram("api_request_latency_seconds", "API Request Latency", ["endpoint"])

def setup_observability(app: FastAPI, service_name: str, otlp_endpoint: str = "http://jaeger:4317"):
    """
    Hooks OpenTelemetry and Prometheus into a FastAPI app instance.
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)

    if getattr(app, "_is_instrumented", False):
        return app

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    try:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info(f"OTLP tracing configured: {otlp_endpoint}")
    except Exception as e:
        logger.warning(f"OTLP exporter setup failed: {e}")

    # Instrument FastAPI for automatic OpenTelemetry tracing
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    app._is_instrumented = True

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        import time
        start_time = time.time()
        
        # Adding manual span for business logic isolation
        with tracer.start_as_current_span(f"HTTP {request.method} {request.url.path}") as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            
            response = await call_next(request)
            
            process_time = time.time() - start_time
            REQUEST_LATENCY.labels(endpoint=request.url.path).observe(process_time)
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                http_status=response.status_code
            ).inc()
            
            span.set_attribute("http.status_code", response.status_code)
            return response

    @app.get("/metrics")
    def export_metrics():
        """Expose Prometheus metrics endpoint"""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    logger.info(f"Observability engine attached to {service_name}")
    return app
