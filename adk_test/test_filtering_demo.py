#!/usr/bin/env python3
"""
Demo script showing how the function call filtering works.
This doesn't require the Google ADK to be installed.
"""

class MockPart:
    """Mock part that simulates content parts."""
    def __init__(self, text=None, function_call=None):
        if text:
            self.text = text
        if function_call:
            self.function_call = function_call

class MockContent:
    """Mock content that simulates event content."""
    def __init__(self, parts):
        self.parts = parts

class MockEvent:
    """Mock event that simulates ADK events."""
    def __init__(self, content=None, author=None):
        self.content = content
        self.author = author

def should_filter_event(event, filter_function_calls=True):
    """
    Simulates the _should_filter_event method.
    """
    if not filter_function_calls:
        return False
        
    # Filter out events that contain function calls
    if event.content and event.content.parts:
        for part in event.content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                return True
    
    return False

def demo_filtering():
    """Demonstrate the filtering in action."""
    print("🔍 Function Call Filtering Demo")
    print("=" * 40)
    
    # Create sample events
    events = [
        MockEvent(
            content=MockContent([MockPart(text="Hello, how can I help you?")]),
            author="assistant"
        ),
        MockEvent(
            content=MockContent([MockPart(text="What's the weather in New York?")]),
            author="user"
        ),
        MockEvent(
            content=MockContent([MockPart(function_call={"name": "get_weather", "args": {"city": "New York"}})]),
            author="assistant"
        ),
        MockEvent(
            content=MockContent([MockPart(text="The weather in New York is sunny with a temperature of 25 degrees Celsius.")]),
            author="assistant"
        ),
        MockEvent(
            content=MockContent([MockPart(text="Can you calculate 5 * 10?")]),
            author="user"
        ),
        MockEvent(
            content=MockContent([MockPart(function_call={"name": "run_python", "args": {"code": "result = 5 * 10"}})]),
            author="assistant"
        ),
        MockEvent(
            content=MockContent([MockPart(text="The result is 50.")]),
            author="assistant"
        )
    ]
    
    print(f"📝 Original events: {len(events)}")
    for i, event in enumerate(events):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(f"  {i+1}. [TEXT] {part.text}")
                elif hasattr(part, 'function_call'):
                    print(f"  {i+1}. [FUNCTION_CALL] {part.function_call['name']}")
    
    print("\n🔄 Filtering function calls...")
    
    # Apply filtering
    filtered_events = []
    for event in events:
        if not should_filter_event(event, filter_function_calls=True):
            filtered_events.append(event)
        else:
            print(f"  ❌ Filtered out function call event")
    
    print(f"\n✅ Filtered events: {len(filtered_events)}")
    for i, event in enumerate(filtered_events):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'text'):
                    print(f"  {i+1}. [TEXT] {part.text}")
    
    print(f"\n📊 Summary:")
    print(f"  Original events: {len(events)}")
    print(f"  Filtered events: {len(filtered_events)}")
    print(f"  Function calls removed: {len(events) - len(filtered_events)}")

if __name__ == "__main__":
    demo_filtering()