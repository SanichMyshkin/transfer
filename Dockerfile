FROM sonatype/nexus3:3.44.0

COPY nexus-plugins/ /opt/sonatype/nexus/deploy/
