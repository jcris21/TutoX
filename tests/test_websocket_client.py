import asyncio
import json
import time
from uuid import uuid4

import websockets

BASE_URL = "ws://localhost:8002"


async def test_websocket_interactions():
    """Complete WebSocket testing flow"""

    # Generate test IDs
    session_id = str(uuid4())
    user_login = "test_user"
    db = "test_db"

    ws_url = f"{BASE_URL}/ws?session_id={session_id}&user_login={user_login}&db={db}"

    print(f"Connecting to {ws_url}\n")

    try:
        # Set timeout to 120 seconds (2 minutes)
        async with websockets.connect(
            ws_url, ping_interval=20, ping_timeout=60
        ) as websocket:
            # Test 1: Receive connection confirmation
            print("=" * 50)
            print("TEST 1: Connection Confirmation")
            print("=" * 50)

            response = await websocket.recv()
            print(f"Received: {json.dumps(json.loads(response), indent=2)}\n")

            # Test 2: Send chat message
            print("=" * 50)
            print("TEST 2: Chat Message")
            print("=" * 50)

            chat_message = {
                "type": "chat",
                "message": "What is the stock picking type process?",
            }

            await websocket.send(json.dumps(chat_message))
            print(f"Sent: {json.dumps(chat_message, indent=2)}")

            # IMPORTANT: Wait longer for the response
            response = await asyncio.wait_for(
                websocket.recv(), timeout=120  # 2 minutos de timeout
            )
            response_data = json.loads(response)
            print(f"Received: {json.dumps(response_data, indent=2)}")
            chat_interaction_id = response_data.get("interaction_id")
            print(f"Interaction ID: {chat_interaction_id}\n")

            await asyncio.sleep(1)

            # Test 3: Send feedback event
            print("=" * 50)
            print("TEST 3: Feedback Event")
            print("=" * 50)

            feedback_message = {
                "type": "feedback_event",
                "event_name": "ai_feedback",
                "event_data": {
                    "message_body_text": "Great response! The explanation was clear.",
                    "message_body_html": "<p>Great response! The explanation was clear.</p>",
                    "message_uid": str(uuid4()),
                    "vote": "up",
                    "saved_to_odoo": True,
                    "rpc_result": {"id": 1},
                },
            }

            await websocket.send(json.dumps(feedback_message))
            print(f"Sent: {json.dumps(feedback_message, indent=2)}")

            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Received: {json.dumps(response_data, indent=2)}")
            feedback_interaction_id = response_data.get("interaction_id")
            print(f"Interaction ID: {feedback_interaction_id}\n")

            await asyncio.sleep(1)

            # Test 4: Send UI event
            print("=" * 50)
            print("TEST 4: UI Event")
            print("=" * 50)

            ui_message = {
                "type": "ui_event",
                "event_name": "button_click",
                "event_data": {
                    "button_id": "confirm_picking",
                    "page": "stock_picking_form",
                    "timestamp": time.time(),
                },
            }

            await websocket.send(json.dumps(ui_message))
            print(f"Sent: {json.dumps(ui_message, indent=2)}")

            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Received: {json.dumps(response_data, indent=2)}")
            ui_interaction_id = response_data.get("interaction_id")
            print(f"Interaction ID: {ui_interaction_id}\n")

            await asyncio.sleep(1)

            # Test 5: Context update
            print("=" * 50)
            print("TEST 5: Context Update")
            print("=" * 50)

            context_message = {
                "type": "context_update",
                "context": {
                    "model": "stock.picking.type",
                    "form_id": 123,
                    "user_role": "warehouse_manager",
                },
            }

            await websocket.send(json.dumps(context_message))
            print(f"Sent: {json.dumps(context_message, indent=2)}")

            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Received: {json.dumps(response_data, indent=2)}\n")

            # Summary
            print("=" * 50)
            print("TESTING SUMMARY")
            print("=" * 50)
            print(f"Session ID: {session_id}")
            print(f"User Login: {user_login}")
            print(f"Chat Interaction ID: {chat_interaction_id}")
            print(f"Feedback Interaction ID: {feedback_interaction_id}")
            print(f"UI Interaction ID: {ui_interaction_id}")
            print("\nAll interactions should be saved to ChromaDB segmented by user!")
            print("Use the /user/interactions endpoint to verify.\n")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_websocket_interactions())
