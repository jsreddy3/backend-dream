#!/usr/bin/env python3
"""Test script for interpretation questions functionality."""

import asyncio
import httpx
import json
from uuid import UUID

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "Test1234!"


async def login(client: httpx.AsyncClient) -> str:
    """Login and get auth token."""
    response = await client.post(
        f"{API_BASE_URL}/auth/token",
        data={
            "username": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
        }
    )
    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        raise Exception("Login failed")


async def get_dreams(client: httpx.AsyncClient, token: str):
    """Get all dreams for the user."""
    response = await client.get(
        f"{API_BASE_URL}/dreams/",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get dreams: {response.status_code} - {response.text}")
        return []


async def generate_summary(client: httpx.AsyncClient, token: str, dream_id: str):
    """Generate title and summary for a dream."""
    print(f"\n📝 Generating summary for dream {dream_id}...")
    response = await client.post(
        f"{API_BASE_URL}/dreams/{dream_id}/generate-summary",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Generated title: {data['title']}")
        print(f"✅ Summary: {data['summary']}")
        return data
    else:
        print(f"❌ Failed to generate summary: {response.status_code} - {response.text}")
        return None


async def generate_questions(client: httpx.AsyncClient, token: str, dream_id: str):
    """Generate interpretation questions for a dream."""
    print(f"\n❓ Generating interpretation questions for dream {dream_id}...")
    response = await client.post(
        f"{API_BASE_URL}/dreams/{dream_id}/generate-questions",
        headers={"Authorization": f"Bearer {token}"},
        json={"num_questions": 3, "num_choices": 3}
    )
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Generated {len(data['questions'])} questions")
        return data['questions']
    else:
        print(f"❌ Failed to generate questions: {response.status_code} - {response.text}")
        return None


async def get_questions(client: httpx.AsyncClient, token: str, dream_id: str):
    """Get all questions for a dream."""
    response = await client.get(
        f"{API_BASE_URL}/dreams/{dream_id}/questions",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get questions: {response.status_code} - {response.text}")
        return []


async def answer_question(client: httpx.AsyncClient, token: str, dream_id: str, question_id: str, choice_id: str = None, custom_answer: str = None):
    """Record an answer to a question."""
    data = {"question_id": question_id}
    if choice_id:
        data["choice_id"] = choice_id
    if custom_answer:
        data["custom_answer"] = custom_answer
    
    response = await client.post(
        f"{API_BASE_URL}/dreams/{dream_id}/answer",
        headers={"Authorization": f"Bearer {token}"},
        json=data
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to record answer: {response.status_code} - {response.text}")
        return None


async def get_answers(client: httpx.AsyncClient, token: str, dream_id: str):
    """Get all answers for a dream."""
    response = await client.get(
        f"{API_BASE_URL}/dreams/{dream_id}/answers",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get answers: {response.status_code} - {response.text}")
        return []


async def main():
    """Main test function."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Login
        print("🔐 Logging in...")
        token = await login(client)
        print("✅ Login successful")
        
        # Get dreams
        print("\n🌙 Getting dreams...")
        dreams = await get_dreams(client, token)
        print(f"Found {len(dreams)} dreams")
        
        # Find a dream with transcript
        dream_with_transcript = None
        for dream in dreams:
            if dream.get('transcript'):
                dream_with_transcript = dream
                break
        
        if not dream_with_transcript:
            print("❌ No dreams with transcripts found")
            return
        
        dream_id = dream_with_transcript['id']
        print(f"\n🎯 Using dream: {dream_id}")
        print(f"   Title: {dream_with_transcript.get('title', 'No title')}")
        print(f"   Transcript preview: {dream_with_transcript['transcript'][:200]}...")
        
        # Generate summary if not already present
        if not dream_with_transcript.get('summary'):
            await generate_summary(client, token, dream_id)
        else:
            print(f"\n✅ Dream already has summary: {dream_with_transcript['summary'][:200]}...")
        
        # Generate interpretation questions
        questions = await generate_questions(client, token, dream_id)
        
        if questions:
            print("\n📋 Generated Questions:")
            for i, q in enumerate(questions, 1):
                print(f"\n{i}. {q['question_text']}")
                for j, choice in enumerate(q['choices']):
                    print(f"   {chr(97+j)}) {choice['choice_text']}")
            
            # Answer some questions
            print("\n💬 Recording answers...")
            
            # Answer first question with a predefined choice
            if len(questions) > 0:
                q1 = questions[0]
                if len(q1['choices']) > 0:
                    choice = q1['choices'][0]  # Select first choice
                    answer1 = await answer_question(client, token, dream_id, q1['id'], choice['id'])
                    if answer1:
                        print(f"✅ Answered question 1 with choice: {choice['choice_text']}")
            
            # Answer second question with custom answer
            if len(questions) > 1:
                q2 = questions[1]
                custom_text = "This reminds me of a childhood memory about feeling lost"
                answer2 = await answer_question(client, token, dream_id, q2['id'], custom_answer=custom_text)
                if answer2:
                    print(f"✅ Answered question 2 with custom: {custom_text}")
            
            # Get all answers
            print("\n📊 Retrieving all answers...")
            answers = await get_answers(client, token, dream_id)
            print(f"Found {len(answers)} answers")
            for answer in answers:
                print(f"  - Question {answer['question_id'][:8]}...")
                if answer.get('custom_answer'):
                    print(f"    Custom: {answer['custom_answer']}")
                else:
                    print(f"    Choice: {answer['selected_choice_id'][:8]}...")
            
            # Test updating an answer
            if len(questions) > 0 and len(questions[0]['choices']) > 1:
                print("\n🔄 Testing answer update...")
                q1 = questions[0]
                new_choice = q1['choices'][1]  # Select second choice
                updated = await answer_question(client, token, dream_id, q1['id'], new_choice['id'])
                if updated:
                    print(f"✅ Updated answer to: {new_choice['choice_text']}")


if __name__ == "__main__":
    asyncio.run(main())