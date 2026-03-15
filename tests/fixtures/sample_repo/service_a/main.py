"""Service A - HTTP + Database integration patterns."""
import requests
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
engine = create_engine("postgresql://localhost/service_a")
Session = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)


def get_user_from_service_b(user_id: str) -> dict:
    """Call service B to get user details."""
    response = requests.get(f"http://service-b:8000/api/users/{user_id}")
    return response.json()


def create_user(name: str) -> User:
    session = Session()
    user = User(name=name)
    session.add(user)
    session.commit()
    return user
