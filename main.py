from calender_assistant import CalendarAssistant

assistant = CalendarAssistant()

def calendar_menu():
    while True:
        print("\n===== 📅 Calendar Menu =====")
        print("1. Show today's events")
        print("2. Show tomorrow's events")
        print("3. List all upcoming events")
        print("4. Create new event")
        print("5. Find free slots")
        print("6. Show this week's events")
        print("7. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            assistant.list_today_events()
        elif choice == '2':
            assistant.list_tomorrow_events()
        elif choice == '3':
            assistant.list_all_upcoming_events()
        elif choice == '4':
            summary = input("Enter event title: ")
            start = input("Enter start time (YYYY-MM-DDTHH:MM:SS): ")
            end = input("Enter end time (YYYY-MM-DDTHH:MM:SS): ")
            email = input("Enter attendee email (leave blank if none): ")
            assistant.create_event(summary, start, end, email if email else None)
        elif choice == '5':
            assistant.find_free_slots()
        elif choice == '6':
            assistant.show_week_events()
        elif choice == '7':
            print("👋 Goodbye!")
            break
        else:
            print("❗ Invalid choice. Please select again.")

def process_nlp_command():
    user_input = input("Enter your command (e.g., 'Show my events for today'): ")
    if "today" in user_input.lower():
        print("NLP Output: Sure, go ahead and say: \n\n\"Give me a list of events I can expect today\"")
        assistant.list_today_events()
    elif "tomorrow" in user_input.lower():
        assistant.list_tomorrow_events()
    else:
        print("NLP could not match your intent. Showing calendar menu.")
    calendar_menu()

if __name__ == "__main__":
    process_nlp_command()
