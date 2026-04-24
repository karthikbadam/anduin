# PyFlink job image. Ships Flink 1.19 + Python + PyFlink + the jars we need
# for Avro-Confluent Kafka source and JSON Kafka sink.
FROM flink:1.19.2-scala_2.12-java17

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-dev curl \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# PyFlink + Avro + astropy-healpix (the Hot Sky Cells job uses it for cell boundaries).
RUN pip3 install --no-cache-dir --break-system-packages \
      'apache-flink==1.19.2' \
      'avro==1.11.3' \
      'fastavro==1.9.*'

# Jars for Kafka Avro-Confluent source and JSON sink.
ENV FLINK_VERSION=1.19.2
ENV KAFKA_CONNECTOR_VER=3.2.0-1.19
RUN curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka-${KAFKA_CONNECTOR_VER}.jar \
      https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR_VER}/flink-sql-connector-kafka-${KAFKA_CONNECTOR_VER}.jar \
 && curl -fsSL -o /opt/flink/lib/flink-sql-avro-confluent-registry-${FLINK_VERSION}.jar \
      https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-avro-confluent-registry/${FLINK_VERSION}/flink-sql-avro-confluent-registry-${FLINK_VERSION}.jar

COPY jobs/ /opt/flink/jobs/

USER flink
