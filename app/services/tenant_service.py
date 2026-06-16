import json
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)
TENANTS_FILE = Path("data/tenants.json")


class TenantService:

    def _load(self) -> Dict:
        if not TENANTS_FILE.exists():
            return {"tenants": {}, "phone_to_tenant": {}, "keyword_to_tenant": {}}
        with open(TENANTS_FILE, "r") as f:
            data = json.load(f)
            data.setdefault("keyword_to_tenant", {})  # backward compatibility
            return data

    def _save(self, data: Dict):
        TENANTS_FILE.parent.mkdir(exist_ok=True)
        with open(TENANTS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def create_tenant(self, tenant_id: str, name: str, keyword: str = None) -> Dict:
        data = self._load()

        if tenant_id in data["tenants"]:
            raise ValueError(f"Tenant '{tenant_id}' already exists.")

        # Auto-generate keyword if not provided — uppercase, no spaces
        if not keyword:
            keyword = tenant_id.upper().replace("_", "")

        keyword = keyword.upper().strip()

        if keyword in data["keyword_to_tenant"]:
            raise ValueError(f"Keyword '{keyword}' is already taken by another tenant.")

        data["tenants"][tenant_id] = {
            "name": name,
            "keyword": keyword,
            "whatsapp_numbers": [],
            "collection_name": f"tenant_{tenant_id}",
        }
        data["keyword_to_tenant"][keyword] = tenant_id
        self._save(data)
        logger.info(f"Created tenant: {tenant_id} with keyword: {keyword}")
        return data["tenants"][tenant_id]

    def get_tenant(self, tenant_id: str) -> Optional[Dict]:
        return self._load()["tenants"].get(tenant_id)

    def list_tenants(self) -> Dict:
        return self._load()["tenants"]

    def register_phone(self, tenant_id: str, phone: str) -> bool:
        data = self._load()
        if tenant_id not in data["tenants"]:
            raise ValueError(f"Tenant '{tenant_id}' does not exist.")

        phone = phone.strip()
        data["phone_to_tenant"][phone] = tenant_id

        if phone not in data["tenants"][tenant_id]["whatsapp_numbers"]:
            data["tenants"][tenant_id]["whatsapp_numbers"].append(phone)

        self._save(data)
        return True

    def get_tenant_by_phone(self, phone: str) -> Optional[str]:
        data = self._load()
        return data["phone_to_tenant"].get(phone.strip())

    def get_tenant_by_keyword(self, keyword: str) -> Optional[str]:
        """
        Core new method: given a keyword like 'RESTAURANT123',
        find which tenant it belongs to.
        """
        data = self._load()
        return data["keyword_to_tenant"].get(keyword.upper().strip())

    def get_collection_name(self, tenant_id: str) -> Optional[str]:
        tenant = self.get_tenant(tenant_id)
        return tenant["collection_name"] if tenant else None