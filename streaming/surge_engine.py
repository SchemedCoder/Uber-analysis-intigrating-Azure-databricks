from pyspark.sql.functions import col, when

def calculate_surge(city, ride_count):
    """
    Standard Python implementation of surge pricing.
    Used for unit testing and simple batch scripts.
    """
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


def get_spark_surge_expression(city_col_name="city", count_col_name="ride_count"):
    """
    Production-grade vectorized expression for PySpark.
    Runs entirely within the JVM to avoid PySpark Python-JVM serialization overhead.
    """
    city_col = col(city_col_name)
    count_col = col(count_col_name)
    
    base_surge = when(count_col > 100, 2.5) \
                .when(count_col > 60, 1.8) \
                .when(count_col > 30, 1.3) \
                .otherwise(1.0)
    
    city_boost = when(city_col.isin("Mumbai", "Delhi", "Bangalore"), 0.2).otherwise(0.0)
    
    return (base_surge + city_boost)
