FROM golang:alpine

RUN apk add --no-cache git gcc libc-dev

RUN go get github.com/mattn/go-sqlite3 && \
    go get golang.org/x/net/publicsuffix && \
    go get github.com/miekg/dns

RUN git clone https://github.com/google/namebench.git /go/src/github.com/google/namebench

WORKDIR /go/src/github.com/google/namebench

RUN go build namebench.go

CMD ./namebench -port 8080