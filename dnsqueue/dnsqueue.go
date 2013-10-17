// dnsqueue is a library for queueing up a large number of DNS requests.
package dnsqueue

import (
	"errors"
	"fmt"
	"github.com/miekg/dns"
	"log"
	"time"
)

// Request contains data for making a DNS request
type Request struct {
	Destination     string
	RecordType      string
	RecordName      string
	VerifySignature bool

	exit bool
}

// Answer contains a single answer returned by a DNS server.
type Answer struct {
	Ttl    uint32
	Name   string
	String string
}

// Result contains metadata relating to a set of DNS server results.
type Result struct {
	Request  Request
	Duration time.Duration
	Answers  []Answer
	Error    string
}

// Queue contains methods and state for setting up a request queue.
type Queue struct {
	Requests    chan *Request
	Results     chan *Result
	WorkerCount int
	Quit        chan bool
}

// StartQueue starts a new queue with max length of X with worker count Y.
func StartQueue(size, workers int) (q *Queue) {
	q = &Queue{
		Requests:    make(chan *Request, size),
		Results:     make(chan *Result, size),
		WorkerCount: workers,
	}
	for i := 0; i < q.WorkerCount; i++ {
		go startWorker(q.Requests, q.Results)
	}
	return
}

// Queue.Add adds a request to the queue. Only blocks if queue is full.
func (q *Queue) Add(dest, record_type, record_name string) {
	q.Requests <- &Request{
		Destination: dest,
		RecordType:  record_type,
		RecordName:  record_name,
	}
}

// Queue.SendDieSignal sends a signal to the workers that they can go home now.
func (q *Queue) SendCompletionSignal() {
	log.Printf("Sending completion signal...")
	for i := 0; i < q.WorkerCount; i++ {
		q.Requests <- &Request{exit: true}
	}
}

// startWorker starts a thread to watch the request channel and populate result channel.
func startWorker(queue <-chan *Request, results chan<- *Result) {
	for request := range queue {
		if request.exit {
			log.Printf("Completion received, worker is done.")
			return
		}
		result, err := SendQuery(request)
		if err != nil {
			log.Printf("Error sending query: %s", err)
		}
		log.Printf("Sending back result: %s", result)
		results <- &result
	}
}

// Send a DNS query via UDP, configured by a Request object. If successful,
// stores response details in Result object, otherwise, returns Result object
// with an error string.
func SendQuery(request *Request) (result Result, err error) {
	log.Printf("Sending query: %s", request)
	result.Request = *request

	record_type, ok := dns.StringToType[request.RecordType]
	if !ok {
		result.Error = fmt.Sprintf("Invalid type: %s", request.RecordType)
		return result, errors.New(result.Error)
	}

	m := new(dns.Msg)
	if request.VerifySignature == true {
		log.Printf("SetEdns0 for %s", request.RecordName)
		m.SetEdns0(4096, true)
	}
	m.SetQuestion(request.RecordName, record_type)
	c := new(dns.Client)
	in, rtt, err := c.Exchange(m, request.Destination)
	// log.Printf("Answer: %s [%d] %s", in, rtt, err)

	result.Duration = rtt
	if err != nil {
		result.Error = err.Error()
	} else {
		for _, rr := range in.Answer {
			answer := Answer{
				Ttl:    rr.Header().Ttl,
				Name:   rr.Header().Name,
				String: rr.String(),
			}
			result.Answers = append(result.Answers, answer)
		}
	}
	return result, nil
}
