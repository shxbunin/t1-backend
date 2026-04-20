FROM alpine:3.20

RUN apk add --no-cache socat

CMD ["socat", "-d", "-d", "TCP-LISTEN:5432,fork,reuseaddr", "TCP:172.30.0.10:5432"]
