from config import Config
import motor.motor_asyncio

class Database:
    def __init__(self, uri, db_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[db_name]
        self.users = self.db.users
        self.bots = self.db.bots
        self.projects = self.db.projects

    # ─── User Management ───────────────────────────────────────────────────────
    async def is_user_exist(self, user_id: int) -> bool:
        return bool(await self.users.find_one({"id": user_id}))

    async def add_user(self, user_id: int, name: str):
        await self.users.insert_one({
            "id": user_id,
            "name": name,
            "is_auth": False,
            "is_banned": False,
        })

    async def get_user(self, user_id: int):
        return await self.users.find_one({"id": user_id})

    async def get_all_users(self):
        return self.users.find({})

    async def total_users_count(self) -> int:
        return await self.users.count_documents({})

    async def delete_user(self, user_id: int):
        await self.users.delete_many({"id": user_id})

    async def ban_user(self, user_id: int):
        await self.users.update_one({"id": user_id}, {"$set": {"is_banned": True}})

    async def unban_user(self, user_id: int):
        await self.users.update_one({"id": user_id}, {"$set": {"is_banned": False}})

    async def is_banned(self, user_id: int) -> bool:
        u = await self.users.find_one({"id": user_id})
        return bool(u and u.get("is_banned"))

    async def auth_user(self, user_id: int):
        await self.users.update_one({"id": user_id}, {"$set": {"is_auth": True}})

    async def unauth_user(self, user_id: int):
        await self.users.update_one({"id": user_id}, {"$set": {"is_auth": False}})

    async def is_auth(self, user_id: int) -> bool:
        u = await self.users.find_one({"id": user_id})
        return bool(u and u.get("is_auth"))

    # ─── Bot/Userbot Management per User ───────────────────────────────────────
    async def add_bot(self, data: dict):
        existing = await self.bots.find_one({"user_id": data["user_id"]})
        if existing:
            await self.bots.replace_one({"user_id": data["user_id"]}, data)
        else:
            await self.bots.insert_one(data)

    async def get_bot(self, user_id: int):
        return await self.bots.find_one({"user_id": user_id})

    async def remove_bot(self, user_id: int):
        await self.bots.delete_many({"user_id": user_id})

    # ─── Project Management ─────────────────────────────────────────────────────
    # Each project: {user_id, name, source_id, destinations: [], filters: {}, forward_tag: bool,
    #                keyword_replace: {enabled: bool, pairs: [{"old": ..., "new": ...}]},
    #                keyword_filter: {enabled: bool, keywords: [...]}}

    async def get_projects(self, user_id: int):
        return [p async for p in self.projects.find({"user_id": user_id})]

    async def count_projects(self, user_id: int) -> int:
        return await self.projects.count_documents({"user_id": user_id})

    async def add_project(self, project: dict):
        await self.projects.insert_one(project)

    async def get_project(self, project_id: str):
        from bson import ObjectId
        return await self.projects.find_one({"_id": ObjectId(project_id)})

    async def update_project(self, project_id: str, data: dict):
        from bson import ObjectId
        await self.projects.update_one({"_id": ObjectId(project_id)}, {"$set": data})

    async def delete_project(self, project_id: str):
        from bson import ObjectId
        await self.projects.delete_one({"_id": ObjectId(project_id)})

    async def total_projects_count(self) -> int:
        return await self.projects.count_documents({})

    def default_filters(self):
        return {
            "text": True,
            "photo": True,
            "video": True,
            "audio": True,
            "document": True,
            "voice": True,
            "animation": True,
            "sticker": True,
            "poll": True,
        }

    def default_keyword_replace(self):
        return {
            "enabled": False,
            "pairs": []   # list of {"old": "...", "new": "..."}
        }

    def default_keyword_filter(self):
        return {
            "enabled": False,
            "keywords": []  # list of strings, max 3
        }

    def default_file_filter(self):
        return {
            "enabled": False,
            "extensions": []  # list of file extensions (without dot), max 3
        }

    def default_keyword_unfilter(self):
        return {
            "enabled": False,
            "keywords": []  # list of prohibited strings, max 3 — if matched, message is skipped
        }

db = Database(Config.DATABASE_URI, Config.DATABASE_NAME)
