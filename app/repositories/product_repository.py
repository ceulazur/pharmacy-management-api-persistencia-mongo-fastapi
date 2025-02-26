from typing import Dict, Any
from bson import ObjectId, errors
from fastapi import HTTPException
from app.models.product import ProductModel
from app.models.common import PaginationParams
from app.config.database import database
from app.utils.mongo_utils import convert_mongo_document
from datetime import datetime

class ProductRepository:
    collection = database.products

    async def create(self, product: ProductModel) -> str:
        try:
            # Validar se o ID do fornecedor é um ObjectId válido
            supplier_id = ObjectId(product.supplier_id)
        except errors.InvalidId:
            raise HTTPException(
                status_code=400,
                detail="Invalid supplier ID format"
            )

        # Verificar se o fornecedor existe
        supplier = await database.suppliers.find_one({"_id": supplier_id})
        if not supplier:
            raise HTTPException(
                status_code=404,
                detail=f"Supplier with ID {product.supplier_id} not found"
            )
            
        result = await self.collection.insert_one(product.model_dump())
        return str(result.inserted_id)

    async def get_by_id(self, id: str) -> Dict[str, Any]:
        document = await self.collection.find_one({"_id": ObjectId(id)})
        return convert_mongo_document(document)

    async def get_all(self, pagination: PaginationParams, filters: Dict = None):
        skip = (pagination.page - 1) * pagination.limit
        
        query = {}
        if filters:
            for key, value in filters.items():
                if value is not None:
                    if isinstance(value, dict):  # For price range queries
                        query[key] = value
                    else:
                        query[key] = value

        cursor = self.collection.find(query)

        if pagination.sort_by:
            sort_order = 1 if pagination.sort_order == "asc" else -1
            cursor = cursor.sort(pagination.sort_by, sort_order)

        total = await self.collection.count_documents(query)
        products = await cursor.skip(skip).limit(pagination.limit).to_list(None)
        
        return {
            "total": total,
            "page": pagination.page,
            "limit": pagination.limit,
            "products": [convert_mongo_document(p) for p in products]
        }

    async def update(self, id: str, update_data: Dict) -> Dict[str, Any]:
        if "supplier_id" in update_data:
            supplier = await database.suppliers.find_one({"_id": ObjectId(update_data["supplier_id"])})
            if not supplier:
                raise HTTPException(status_code=404, detail="Supplier not found")
        
        update_data["updated_at"] = datetime.utcnow()
        await self.collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_data}
        )
        return await self.get_by_id(id)

    async def delete(self, id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count > 0
