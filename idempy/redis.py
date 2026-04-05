from redis import Redis
from redis.exceptions import RedisError

class RedisClient: 
    def __init__(self, host='localhost', port=6379, db=0):
        self.client = Redis(host=host, port=port, db=db)

    def set(self, key, value, ex=None):
        try:
            self.client.set(key, value, ex=ex)
        except RedisError as e:
            print(f"Redis error: {e}")

    def get(self, key):
        try:
            return self.client.get(key)
        except RedisError as e:
            print(f"Redis error: {e}")
            return None

    def delete(self, key):
        try:
            self.client.delete(key)
        except RedisError as e:
            print(f"Redis error: {e}")
    
    def update(self, key, value, ex=None):
        try:
            if self.client.exists(key):
                self.client.set(key, value, ex=ex)
            else:
                print(f"Key {key} does not exist.")
        except RedisError as e:
            print(f"Redis error: {e}")