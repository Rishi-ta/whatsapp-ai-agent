import json
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

TENANTS_FILE = Path("data/tenants.json")


class TenantService:
    """
    Manages tenant registry stored in data/tenants.json.
    
    In Week 4 this becomes a proper database.
    For Week 3, JSON file is simple and easy to inspect/debug.
    """

    def _load(self) -> Dict:
        if not TENANTS_FILE.exists():
            return {"tenants": {}, "phone_to_tenant": {}}
        with open(TENANTS_FILE, "r") as f:
            return json.load(f)

    def _save(self, data: Dict):
        TENANTS_FILE.parent.mkdir(exist_ok=True)
        with open(TENANTS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def create_tenant(self, tenant_id: str, name: str) -> Dict:
        """Create a new business tenant."""
        data = self._load()

        if tenant_id in data["tenants"]:
            raise ValueError(f"Tenant '{tenant_id}' already exists.")

        data["tenants"][tenant_id] = {
            "name": name,
            "whatsapp_numbers": [],
            "collection_name": f"tenant_{tenant_id}",
            "created_at": str(Path(".").stat().st_mtime),
        }
        self._save(data)
        logger.info(f"Created tenant: {tenant_id}")
        return data["tenants"][tenant_id]

    def get_tenant(self, tenant_id: str) -> Optional[Dict]:
        data = self._load()
        return data["tenants"].get(tenant_id)

    def list_tenants(self) -> Dict:
        return self._load()["tenants"]

    def register_phone(self, tenant_id: str, phone: str) -> bool:
        """
        Map a WhatsApp phone number to a tenant.
        This is how the webhook knows which business a message belongs to.
        """
        data = self._load()

        if tenant_id not in data["tenants"]:
            raise ValueError(f"Tenant '{tenant_id}' does not exist.")

        # Normalize phone format
        phone = phone.strip()
        data["phone_to_tenant"][phone] = tenant_id

        if phone not in data["tenants"][tenant_id]["whatsapp_numbers"]:
            data["tenants"][tenant_id]["whatsapp_numbers"].append(phone)

        self._save(data)
        logger.info(f"Registered phone {phone} → tenant {tenant_id}")
        return True

    def get_tenant_by_phone(self, phone: str) -> Optional[str]:
        """
        Core lookup used by the webhook:
        given a WhatsApp number, which tenant does it belong to?
        Returns tenant_id or None if not registered.
        """
        data = self._load()
        return data["phone_to_tenant"].get(phone.strip())

    def get_collection_name(self, tenant_id: str) -> Optional[str]:
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return None
        return tenant["collection_name"]