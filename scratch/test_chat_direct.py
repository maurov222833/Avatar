import sys
import os

avatar_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if avatar_root not in sys.path:
    sys.path.insert(0, avatar_root)

from server import chat_with_avatar, ChatRequest

def test_chat():
    print("Testing chat_with_avatar direct call...")
    try:
        res = chat_with_avatar(ChatRequest(message="Hola Avatar, dime tu estado"))
        print("Response:", res)
    except Exception as e:
        print("EXCEPTION IN CHAT:", type(e), e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chat()
