from functools import cached_property

from fastapi import APIRouter, Depends
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseUserController
from mealie.routes._base.controller import controller
from mealie.schema.personal.enums import RetailStore
from mealie.schema.personal.pantry import (
    ProductImport,
    ProductImportOut,
    ProductOut,
    ProductPagination,
    ProductSearchOut,
)
from mealie.schema.response.pagination import PaginationQuery
from mealie.services.personal.product_service import ProductService

from ._base import run

router = APIRouter(prefix="/households/products", tags=["Personal: Products"])


@controller(router)
class ProductController(BaseUserController):
    @cached_property
    def service(self) -> ProductService:
        return ProductService(self.repos)

    @router.get("", response_model=ProductPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repos.pe_products.page_all(pagination=q, override=ProductOut)
        response.set_pagination_guides(router.url_path_for("get_all"), q.model_dump())
        return response

    @router.get("/search", response_model=ProductSearchOut)
    def search(self, query: str, store: RetailStore | None = None):
        return run(lambda: self.service.search(query, store))

    @router.post("/import", response_model=ProductImportOut, status_code=201)
    def import_product(self, data: ProductImport):
        return run(lambda: self.service.import_product(data))

    @router.get("/{item_id}", response_model=ProductOut)
    def get_one(self, item_id: UUID4):
        return run(lambda: self.service.get_one(item_id))

    @router.delete("/{item_id}", response_model=ProductOut)
    def delete_one(self, item_id: UUID4):
        return run(lambda: self.service.delete(item_id))
