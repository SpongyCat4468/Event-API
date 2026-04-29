from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from models import User, Todo

# Create engine - adjust the database path if needed
DATABASE_URL = "sqlite:///./todos.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def print_separator(title=""):
    print("\n" + "=" * 80)
    if title:
        print(f" {title}")
        print("=" * 80)

def view_database():
    """View all contents of the todos database"""
    
    # Check if tables exist
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print_separator("DATABASE TABLES")
    print(f"Tables found: {tables}")
    
    if not tables:
        print("\n❌ No tables found! Database might be empty or not initialized.")
        return
    
    # View Users
    print_separator("USERS TABLE")
    users = db.query(User).all()
    
    if not users:
        print("No users found.")
    else:
        print(f"Total users: {len(users)}\n")
        for user in users:
            print(f"ID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Created: {user.created_at}")
            print(f"Number of todos: {len(user.todos)}")
            print("-" * 40)
    
    # View Todos
    print_separator("TODOS TABLE")
    todos = db.query(Todo).all()
    
    if not todos:
        print("No todos found.")
    else:
        print(f"Total todos: {len(todos)}\n")
        for i, todo in enumerate(todos, 1):
            print(f"\n📝 Todo #{i}")
            print(f"ID: {todo.id}")
            print(f"Title: {todo.title}")
            print(f"Description: {todo.description or '(no description)'}")
            print(f"Completed: {'✅ Yes' if todo.isCompleted else '❌ No'}")
            print(f"User Email: {todo.user_email}")
            
            # Handle both old and new column names
            notification_times = None
            if hasattr(todo, 'notificationTimes'):
                notification_times = todo.notificationTimes
            elif hasattr(todo, 'notificationTime'):
                notification_times = todo.notificationTime
            
            if notification_times:
                print(f"Notification Times: {notification_times}")
            else:
                print("Notification Times: None")
            
            print(f"Created: {todo.created_at}")
            print(f"Updated: {todo.updated_at}")
            print("-" * 40)
    
    # Summary by user
    print_separator("SUMMARY BY USER")
    for user in users:
        user_todos = db.query(Todo).filter(Todo.user_email == user.email).all()
        completed = sum(1 for t in user_todos if t.isCompleted)
        pending = len(user_todos) - completed
        
        print(f"\n👤 {user.email}")
        print(f"   Total todos: {len(user_todos)}")
        print(f"   Completed: {completed}")
        print(f"   Pending: {pending}")

if __name__ == "__main__":
    try:
        print("\n🔍 Viewing todos.db database contents...\n")
        view_database()
        print_separator("END OF DATABASE VIEW")
        print("\n✅ Database view completed successfully!\n")
    except Exception as e:
        print(f"\n❌ Error viewing database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()