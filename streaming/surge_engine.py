def calculate_surge(city, ride_count):
    base = 1.0

    if ride_count > 100:
        base = 2.5
    elif ride_count > 60:
        base = 1.8
    elif ride_count > 30:
        base = 1.3

    if city in ["Mumbai", "Delhi", "Bangalore"]:
        base += 0.2

    return round(base, 2)
