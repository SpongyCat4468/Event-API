from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Todo API", version="1.0.0")

# CORS middleware for Android app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Android app domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ ROOT ============

@app.get("/")
def root():
    return {"message": "API Connected", "version": "1.0.0"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return {"status": "healthy", "database": "connected"}

# ============ USER ENDPOINTS ============

@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = models.User(email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users/{email}", response_model=schemas.UserResponse)
def get_user(email: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ============ TODO ENDPOINTS ============

@app.post("/todos/", response_model=schemas.TodoResponse)
def create_todo(
    gmail: str = Query(..., description="User email"),
    todo: schemas.TodoCreate = Body(..., description="Todo data"),
    db: Session = Depends(get_db)
):
    """Create a new todo for a user. Auto-creates user if doesn't exist."""
    # Log the received data for debugging
    print(f"Received create todo request for: {gmail}")
    print(f"Todo data: {todo}")
    
    user = db.query(models.User).filter(models.User.email == gmail).first()
    if not user:
        user = models.User(email=gmail)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    new_todo = models.Todo(**todo.model_dump(), user_email=gmail)
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    
    print(f"Created todo with ID: {new_todo.id}")
    return new_todo

@app.get("/todos/{gmail}", response_model=List[schemas.TodoResponse])
def get_todos(
    gmail: str,
    skip: int = 0,
    limit: int = 100,
    completed: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get all todos for a user with optional filtering."""
    user = db.query(models.User).filter(models.User.email == gmail).first()
    if not user:
        # Auto-create user if doesn't exist
        user = models.User(email=gmail)
        db.add(user)
        db.commit()
        db.refresh(user)
        return []
    
    query = db.query(models.Todo).filter(models.Todo.user_email == gmail)
    
    if completed is not None:
        query = query.filter(models.Todo.isCompleted == completed)
    
    return query.offset(skip).limit(limit).all()

@app.get("/todos/{gmail}/{todo_id}", response_model=schemas.TodoResponse)
def get_todo(gmail: str, todo_id: int, db: Session = Depends(get_db)):
    """Get a specific todo by ID."""
    todo = db.query(models.Todo).filter(
        models.Todo.id == todo_id,
        models.Todo.user_email == gmail
    ).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo

@app.put("/todos/{gmail}/{todo_id}", response_model=schemas.TodoResponse)
def update_todo(
    gmail: str,
    todo_id: int,
    todo_update: schemas.TodoUpdate,
    db: Session = Depends(get_db)
):
    """Update a todo. Only provided fields will be updated."""
    todo = db.query(models.Todo).filter(
        models.Todo.id == todo_id,
        models.Todo.user_email == gmail
    ).first()
    
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    update_data = todo_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(todo, key, value)
    
    db.commit()
    db.refresh(todo)
    return todo

@app.patch("/todos/{gmail}/{todo_id}/toggle", response_model=schemas.TodoResponse)
def toggle_todo(gmail: str, todo_id: int, db: Session = Depends(get_db)):
    """Toggle the completion status of a todo."""
    todo = db.query(models.Todo).filter(
        models.Todo.id == todo_id,
        models.Todo.user_email == gmail
    ).first()
    
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    todo.isCompleted = not todo.isCompleted
    db.commit()
    db.refresh(todo)
    return todo

@app.delete("/todos/{gmail}/{todo_id}")
def delete_todo(gmail: str, todo_id: int, db: Session = Depends(get_db)):
    """Delete a specific todo."""
    todo = db.query(models.Todo).filter(
        models.Todo.id == todo_id,
        models.Todo.user_email == gmail
    ).first()
    
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    db.delete(todo)
    db.commit()
    return {"message": "Todo deleted successfully", "id": todo_id}

@app.delete("/todos/{gmail}")
def delete_all_todos(gmail: str, db: Session = Depends(get_db)):
    """Delete all todos for a user."""
    user = db.query(models.User).filter(models.User.email == gmail).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    deleted_count = db.query(models.Todo).filter(models.Todo.user_email == gmail).delete()
    db.commit()
    return {"message": "All todos deleted successfully", "count": deleted_count}

@app.get("/todos/{gmail}/search", response_model=List[schemas.TodoResponse])
def search_todos(gmail: str, q: str, db: Session = Depends(get_db)):
    """Search todos by title."""
    todos = db.query(models.Todo).filter(
        models.Todo.user_email == gmail,
        models.Todo.title.contains(q)
    ).all()
    return todos

@app.get("/todos/{gmail}/stats")
def get_stats(gmail: str, db: Session = Depends(get_db)):
    """Get statistics about user's todos."""
    total = db.query(models.Todo).filter(models.Todo.user_email == gmail).count()
    completed = db.query(models.Todo).filter(
        models.Todo.user_email == gmail,
        models.Todo.isCompleted == True
    ).count()
    
    return {
        "total": total,
        "completed": completed,
        "pending": total - completed,
        "completion_rate": round((completed / total * 100), 2) if total > 0 else 0
    }

@app.post("/todos/{gmail}/bulk-create", response_model=List[schemas.TodoResponse])
def bulk_create_todos(gmail: str, todos: List[schemas.TodoCreate], db: Session = Depends(get_db)):
    """Create multiple todos at once."""
    user = db.query(models.User).filter(models.User.email == gmail).first()
    if not user:
        user = models.User(email=gmail)
        db.add(user)
        db.commit()
        db.refresh(user)
    
    new_todos = [models.Todo(**todo.model_dump(), user_email=gmail) for todo in todos]
    db.add_all(new_todos)
    db.commit()
    
    for todo in new_todos:
        db.refresh(todo)
    
    return new_todos