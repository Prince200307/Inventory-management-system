from fastapi import FastAPI, HTTPException, Query, status
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import database
from datetime import datetime

# ========== LIFESPAN MANAGEMENT ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    Replaces the deprecated @app.on_event("startup")
    """
    # Startup
    try:
        database.setup_database()
        print("✅ Database connection established.")
    except Exception as e:
        print(f"❌ Error connecting to the database: {e}")
        raise

    yield  # This is where the app runs

    # Shutdown (optional - add cleanup logic here if needed)
    print("🛑 Shutting down...")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Inventory Management API",
    description="RESTful API for managing inventory with SQLite database",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan  # Add the lifespan context manager
)
#==================================Pydantic models ==================================

"""
Model for creating a new inventory item
"""
class ProductCreate(BaseModel):
    model_config= ConfigDict(str_strip_whitespace=True)
    product_name: str = Field(..., min_length=1, max_length=100, description="Name of the item (Aplha-numeric only)")
    quantity: int = Field(..., ge=0, description="Initial quantity of the item (must be non-negative)")

    @field_validator('product_name')
    @classmethod
    def validate_product_name(cls, v):
        """Validate that product name is alphanumeric"""
        if not v.isalnum():
            raise ValueError('Product name must be alphanumeric')
        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        """Validate that quantity is non-negative"""
        if v < 0:
            raise ValueError('Quantity must be non-negative')
        return v

class ProductUpdate(BaseModel):
    '''
    Model for updating an existing inventory item
    '''
    quantity: Optional[int] = Field(None, ge=0, description="Updated quantity of the item (must be non-negative)")

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        """Validate that quantity is non-negative"""
        if v is not None and v < 0:
            raise ValueError('Quantity must be non-negative')
        return v

class QuantityAdjust(BaseModel):
    '''
    Model for adjusting the quantity of an inventory item
    '''
    quantity: int = Field(..., gt=0, alias="adjustment", description="Adjustment value (positive or negative)")

    @field_validator('quantity')
    @classmethod
    def validate_adjustment(cls, v):
        """Validate that adjustment is not zero"""
        if v == 0:
            raise ValueError('Adjustment must be non-zero')
        return v

class OrderItem(BaseModel):
    '''Model for ordering an inventory item'''
    product_id: int = Field(..., ge=1, description="ID of the product to order")
    quantity: int = Field(..., ge=1, description="Quantity to order (must be positive)")

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        """Validate that quantity is positive"""
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

class Productresponse(BaseModel):
    '''
    Model for responding with inventory item details
    '''
    id: int
    product_name: str
    quantity: int
    created_at: str
    updated_at: str
    stock_status: Optional[str] = None

class TransactionResponse(BaseModel):
    '''
    Model for responding with transaction details
    '''
    id: int
    product_name: str
    transaction_type: str
    old_quantity: Optional[int] = None
    new_quantity: int
    change_amount: int
    performed_at: str

class ErrorResponse(BaseModel):
    '''
    Model for responding with error details
    '''
    error: str
    detail: Optional[str] = None

class SearchParams(BaseModel):
    '''
    Model for search parameters
    '''
    name: Optional[str] = Field(None, description="Name of the product to search for")
    min_quantity: Optional[int] = Field(None, ge=0, description="Minimum quantity filter (must be non-negative)")
    max_quantity: Optional[int] = Field(None, ge=0, description="Maximum quantity filter (must be non-negative)")
    instock: Optional[bool] = Field(None, description="Filter for items in stock (True) or out of stock (False)")

# #================================== Lifecycle Events ==================================

# @app.on_event("startup")
# async def startup_event():
#     """
#     Initialize the database connection on application startup
#     """
#     try:
#         database.setup_database()
#         print("Database connection established.")
#     except Exception as e:
#         print(f"Error connecting to the database: {e}")
#         raise

#================================== Application Routes ==================================

@app.get("/")
async def read_root():
    """
    Root endpoint to check if the API is running
    """
    return {
        "message": "Inventory Management API is running.",
        "version": "1.0.0",
        "endpoints": {
            "products": "/products",
            "transactions": "/transactions",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

#================================== Health Check Endpoint ==================================

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint to verify API is operational
    """
    try:
        # try to connect with the database
        with database.get_db_connection() as conn:
            cursor= conn.cursor
            cursor.execute("SELECT 1")
            db_status= "healthy"
    except Exception as e:
        db_status= f"unhealthy: {e}"

    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

#=================================== Product endpoints ===================================

@app.post(
    "/products",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    tags= ["Products"],
    responses= {
        201: {"model": Productresponse, "description": "Product created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input data"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
async def create_product(product: ProductCreate):
    """
    Create a new inventory item
    - Product name must be alphanumeric
    - Quantity must be non-negative
    returns the created product details with its ID
    """
    try:
        result= database.create_product(product_name=product.product_name, quantity=product.quantity)
        return {"message": "Product created successfully", "product": result}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

@app.get(
    "/products/",
    response_model=List[Productresponse],
    tags= ["Products"],
    responses={
        200: {"description": "List of all products"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_all_products():
    '''
    Get all products in the inventory
    returns a list of all products with their details
    '''
    try:
        products= database.get_all_products()
        return products
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

@app.get(
    "/products/{product_id}",
    response_model=Productresponse,
    tags= ["Products"],
    responses={200: {"description": "Product found"},
        404: {"model": ErrorResponse, "description": "Product not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_product_by_id(product_id: int):
    '''
    Get a product by its ID
    returns the product details if found
    '''
    try:
        product= database.get_product_by_id(product_id=product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found")
        return product
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

@app.put(
    "/products/{product_id}/quantity",
    response_model=dict,
    tags= ["Products"],
    responses={
        200: {"model": Productresponse, "description": "Product updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input data"},
        404: {"model": ErrorResponse, "description": "Product not found"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
async def update_product_quantity(product_id: int, update: ProductUpdate):
    '''
    Update the quantity of an existing inventory item
    - Quantity must be non-negative
    returns the updated product details
    '''
    try:
        result= database.update_product_quantity(product_id=product_id, new_quantity=update.quantity)
        return {"message": "Product updated successfully", "product": result}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except LookupError as le:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(le))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

@app.post(
    "/products/{product_id}/add",
    response_model=dict,
    tags= ["Products"],
    responses={
        200: {"model": Productresponse, "description": "Quantity adjusted successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input data"},
        404: {"model": ErrorResponse, "description": "Product not found"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
async def add_product_quantity(product_id: int, adjust: QuantityAdjust):
    '''
    Add to the quantity of an existing inventory item
    - Adjustment must be non-zero
    returns the updated product details
    '''
    try:
        result= database.add_quantity_to_product(product_id=product_id, add_quantity=adjust.quantity)
        return {"message": "Quantity adjusted successfully", "product": result}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except LookupError as le:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(le))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

@app.post(
    "/products/{product_id}/order",
    response_model=dict,
    tags= ["Products"],
    responses={
        200: {"model": Productresponse, "description": "Quantity adjusted successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input data"},
        404: {"model": ErrorResponse, "description": "Product not found"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
async def order_product(product_id: int, order: OrderItem):
    '''
    Place an order (reduce product quantity)
    -quantity: Quantity to order (must be >0)
    will fail if insufficient stock is available
    '''
    try:
        result = database.order_product(product_id=product_id, order_quantity= order.quantity)
        return {"message": "Quantity adjusted successfully", "product": result}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except LookupError as le:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(le))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

@app.delete(
    "/products/{product_id}",
    response_model=dict,
    tags= ["Products"],
    responses={
        200: {"description": "Product deleted successfully"},
        404: {"model": ErrorResponse, "description": "Product not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def delete_product(product_id: int):
    '''
    Delete a product from the inventory by its ID
    returns a success message upon deletion
    '''
    try:
        result= database.delete_product(product_id=product_id)
        return result
    except LookupError as le:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(le))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

#=================================== Transaction endpoints ===================================

@app.get(
    "/transactions/",
    response_model=List[TransactionResponse],
    tags= ["Transactions"],
    responses={
        200: {"description": "List of all transactions"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_all_transactions(limit:int= Query(50, ge=1, le=1000, description="Maximum number of transactions to return")):
    '''
    Get recent inventory transactions
    - limit: Number of transactions to return (default: 50, max: 100)
    '''
    try:
        transactions= database.get_all_transactions()
        return transactions
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

@app.get(
    "/products/{product_id}/transactions",
    response_model= List[TransactionResponse],
    tags= ["Transactions"],
    responses={
        200: {"description": "List all transactions of the product"},
        404: {"model": ErrorResponse, "description": "Product not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_product_transactions(product_id: int):
    '''
    Get all transactions for a specific product by its ID
    returns a list of transactions related to the product
    '''
    product= database.get_product_by_id(product_id=product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with ID {product_id} not found")

    try:
        transactions= database.get_transactions_by_product(product_id=product_id)
        return transactions
    except LookupError as le:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(le))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

#=================================== Utility endpoints ===================================

@app.get(
    "/stats",
    response_model= dict,
    tags= ["Utilities"],
    responses={
        200: {"description": "Inventory statistics"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_stats():
    '''
    Get inventory statistics
    returns total products, total quantity, and out-of-stock items
    '''
    try:
        stats= database.get_database_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

@app.post(
    "/backup",
    response_model= dict,
    tags= ["Utilities"],
    responses={
        200: {"description": "Database backup created successfully"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def backup_database():
    '''
    Create a backup of the database
    returns the path to the backup file
    '''
    try:
        backup_path= database.backup_database()
        return {"status": True, "message": "Database backup created successfully", "backup_path": backup_path}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

#=================================== Search endpoint ===================================

@app.get(
    "/search",
    response_model= List[Productresponse],
    tags= ["Products"],
    responses={
        200: {"description": "Search results"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def search_products(
    name: Optional[str] = Query(None, description="Name of the product to search for"),
    min_quantity: Optional[int] = Query(None, ge=0, description="Minimum quantity filter (must be non-negative)"),
    max_quantity: Optional[int] = Query(None, ge=0, description="Maximum quantity filter (must be non-negative)"),
    instock: Optional[bool] = Query(None, description="Filter for items in stock (True) or out of stock (False)")
):
    '''
    Search products based on various criteria
    - name: Partial or full name of the product
    - min_quantity: Minimum quantity filter
    - max_quantity: Maximum quantity filter
    - instock: Filter for items in stock or out of stock
    returns a list of products matching the search criteria
    '''
    try:
        all_products= database.get_all_products()
        filtered_products= []
        if min_quantity > max_quantity and min_quantity is not None and max_quantity is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_quantity cannot be greater than max_quantity")
        for product in all_products:
            if name and name.lower() not in product['product_name'].lower():
                continue
            if min_quantity is not None and product['quantity'] < min_quantity:
                continue
            if max_quantity is not None and product['quantity'] > max_quantity:
                continue
            if instock is not None:
                if instock and product['quantity'] <= 0:
                    continue
                if not instock and product['quantity'] > 0:
                    continue
            filtered_products.append(product)
        return filtered_products
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {str(e)}")

#=================================== Bulk Import Endpoint ===================================

class BulkProduct(BaseModel):
    '''
    Model for bulk product import
    '''
    products: List[ProductCreate] = Field(..., min_items=1, max_items=100, description="List of products to import")

@app.post(
    "/products/bulk_import",
    response_model= dict,
    tags= ["Products"],
    responses={
        201: {"description": "Bulk import completed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input data"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
async def bulk_import_products(bulk: BulkProduct):
    '''
    Bulk import multiple products into the inventory
    - products: List of products to import (max 100)
    returns the number of successfully imported products
    '''
    results= {
        "success": [],
        "failed": []
    }
    for product in bulk.products:
        try:
            result= database.create_product(product_name=product.product_name, quantity=product.quantity)
            results["success"].append(result)
        except Exception as e:
            results["failed"].append({"product_name": product.product_name, "error": str(e)})
    return {"message": f"Bulk create completed. Success: {len(results['success'])}, Failed: {len(results['failed'])}", "results": results}

#=================================== Error Handling ===================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    '''
    Custom HTTP exception handler
    '''
    return JSONResponse(
        status_code= exc.status_code,
        content= {
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )

#=================================== Run the application ===================================
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Inventory Management API...")
    print("📚 API Documentation available at: http://localhost:8000/docs")
    print("📖 Alternative docs at: http://localhost:8000/redoc")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )