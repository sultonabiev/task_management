from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from passlib.context import CryptContext
from typing import List

tags_metadata = [
    {"name": "Пользователи"},
    {"name": "Задачи"},
    {"name": "Аутентификация"},
    {"name": "Сайт"}
]

app = FastAPI(openapi_tags=tags_metadata)

class Task(BaseModel):
    name: str = None
    assigned_to: str = None
    status: bool = False
    details: str = None


class User(BaseModel):
    username: str = None
    password: str = None
    supervisor: bool = False

Base = declarative_base()

class DBTask(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    details = Column(String)
    assigned_to = Column(String)
    status = Column(Boolean, default=False)
    completed_by = Column(String, default=None)  # новое поле

class DBUser(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    hashed_password = Column(String)
    supervisor = Column(Boolean, default=False)

engine = create_engine("sqlite:///./app.db")
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db)):
    user = db.query(DBUser).first()
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def get_all_users(db: Session = Depends(get_db)):
    users = db.query(DBUser).all()
    return users

@app.on_event("startup")
async def startup_event():
    with SessionLocal() as db:
        user = db.query(DBUser).filter(DBUser.username == "Admin").first()
        if not user:
            admin_user = DBUser(username="Admin", hashed_password=pwd_context.hash("Admin"))
            db.add(admin_user)
            db.commit()

@app.get("/", response_class=HTMLResponse, tags=["Сайт"])
async def read_root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", tags=["Аутентификация"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"access_token": user.username, "token_type": "bearer"}

@app.get("/task_list", tags=["Задачи"])
async def task_list(db: Session = Depends(get_db)):
    tasks = db.query(DBTask).all()
    return tasks

@app.post("/create_task", tags=["Задачи"])
async def create_task(task: Task, current_user: DBUser = Depends(get_current_user), all_users: List[DBUser] = Depends(get_all_users), db: Session = Depends(get_db)):
    db_task = DBTask(name=task.name, assigned_to=task.assigned_to, status=task.status, details=task.details)
    db.add(db_task)
    db.commit()
    return {"detail": "Task created successfully"}

@app.post("/complete_task/{task_id}", tags=["Задачи"])
async def complete_task(task_id: int, current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(DBTask).filter(DBTask.id == task_id).first()
    if task:
        task.status = True
        task.completed_by = current_user.username  # сохраняем имя пользователя, который выполнил задачу
        db.commit()
        return {"detail": "Task completed successfully"}
    else:
        raise HTTPException(status_code=404, detail="Task not found")

@app.post("/delete_task/{task_id}", tags=["Задачи"])
async def delete_task(task_id: int, current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(DBTask).filter(DBTask.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
        return {"detail": "Task deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Task not found")

@app.post("/modify_task/{task_id}", tags=["Задачи"])
async def modify_task(task_id: int, new_task: Task, current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(DBTask).filter(DBTask.id == task_id).first()
    if task:
        task.name = new_task.name
        task.assigned_to = new_task.assigned_to
        task.status = new_task.status
        db.commit()
        return {"detail": "Task modified successfully"}
    else:
        raise HTTPException(status_code=404, detail="Task not found")

@app.post("/create_user", tags=["Пользователи"])
async def create_user(new_user: User, current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    existing_user = db.query(DBUser).filter(DBUser.username == new_user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = DBUser(username=new_user.username, hashed_password=pwd_context.hash(new_user.password), supervisor=new_user.supervisor)
    db.add(user)
    db.commit()
    return {"detail": "User created successfully"}

@app.post("/delete_user/{username}", tags=["Пользователи"])
async def delete_user(username: str, current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.username == username).first()
    if user:
        db.delete(user)
        db.commit()
        return {"detail": "User deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="User not found")

@app.post("/modify_user/{username}", tags=["Пользователи"])
async def modify_user(username: str, new_user: User, current_user: DBUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.username == username).first()
    if user:
        user.username = new_user.username
        user.hashed_password = pwd_context.hash(new_user.password)
        user.supervisor = new_user.supervisor  # измените это поле
        db.commit()
        return {"detail": "User modified successfully"}
    else:
        raise HTTPException(status_code=404, detail="User not found")

@app.get("/users", tags=["Пользователи"])
async def read_users(db: Session = Depends(get_db)):
    users = db.query(DBUser).all()
    return users

@app.post("/logout", tags=["Аутентификация"])
async def logout(current_user: DBUser = Depends(get_current_user)):
    return {"detail": "Loged out successfuly"}