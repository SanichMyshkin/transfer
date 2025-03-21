up:
	docker compose up -d
	sudo chown -R 200 nexus-data/

del:
	docker compose down -v
	rm -r /root/transfer/nexus-data/

down:
	docker compose down