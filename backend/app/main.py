from fastapi import FastAPI

app = FastAPI(title="Multi-Vendor E-Commerce Marketplace API")


@app.get('/health')
def health_check():
    return {'status': 'ok'}
