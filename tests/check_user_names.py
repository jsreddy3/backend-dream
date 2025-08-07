#!/usr/bin/env python3
"""
Script to verify all users in the database and display their names.
This will show us whether users have names and what those names are.
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get database URL from environment or use the actual database
DATABASE_URL = os.getenv("DB_URL", "postgresql+asyncpg://jsvai:childfrodo10wldd@dreams.cluster-crsosmiwisdr.us-west-1.rds.amazonaws.com:5432/campfire")

async def check_users():
    """Query all users and display their details including names."""
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # First, let's check if the users table exists and get its structure
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'users'
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            
            print("=" * 80)
            print("USERS TABLE STRUCTURE:")
            print("=" * 80)
            for col_name, data_type, nullable in columns:
                print(f"  - {col_name}: {data_type} (nullable: {nullable})")
            
            print("\n" + "=" * 80)
            print("ALL USERS IN DATABASE:")
            print("=" * 80)
            
            # Query all users
            result = await session.execute(text("""
                SELECT id, email, name, google_sub, created, picture
                FROM users
                ORDER BY created DESC
            """))
            
            users = result.fetchall()
            
            if not users:
                print("No users found in the database.")
            else:
                # Statistics
                total_users = len(users)
                users_with_names = sum(1 for u in users if u.name)
                users_without_names = total_users - users_with_names
                
                print(f"\nTotal users: {total_users}")
                print(f"Users with names: {users_with_names}")
                print(f"Users without names: {users_without_names}")
                print(f"Percentage with names: {(users_with_names/total_users)*100:.1f}%\n")
                
                print("-" * 80)
                
                # Display each user
                for i, (user_id, email, name, google_sub, created, picture) in enumerate(users, 1):
                    print(f"\nUser #{i}:")
                    print(f"  ID: {user_id}")
                    print(f"  Email: {email}")
                    print(f"  Name: {name if name else '[NULL - No name set]'}")
                    print(f"  Google Sub: {google_sub[:20]}..." if google_sub and len(google_sub) > 20 else f"  Google Sub: {google_sub}")
                    print(f"  Created: {created}")
                    print(f"  Has Picture: {'Yes' if picture else 'No'}")
                
                print("\n" + "=" * 80)
                print("SUMMARY:")
                print("=" * 80)
                
                # Additional analysis
                if users_without_names > 0:
                    print(f"\n⚠️  {users_without_names} user(s) don't have names set.")
                    print("\nUsers without names (showing email):")
                    for user_id, email, name, _, _, _ in users:
                        if not name:
                            print(f"  - {email}")
                else:
                    print("\n✅ All users have names set!")
                
                # Show name patterns
                print("\nAll user names in the system:")
                for _, email, name, _, _, _ in users:
                    if name:
                        print(f"  - {name} ({email})")
                
        except Exception as e:
            print(f"Error querying database: {e}")
            print(f"Database URL pattern: {DATABASE_URL.split('@')[0]}@...")
    
    await engine.dispose()

if __name__ == "__main__":
    print("Checking users in Dream database...")
    print(f"Using database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'local'}\n")
    asyncio.run(check_users())