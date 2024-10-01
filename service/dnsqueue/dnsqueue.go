// Package dnsqueue is a library for queueing up a large number of DNS requests.
package dnsqueue

import (
	"fmt"
	"github.com/Cellularhacker/logger-go"
	"github.com/goccy/go-json"
	"github.com/miekg/dns"
	"namebench/model/namebench/record"
	"time"
)

// Request contains data for making a DNS request
type Request struct {
	Destination     string `json:"destination"`
	RecordType      string `json:"record_type"`
	RecordName      string `json:"record_name"`
	VerifySignature bool   `json:"verify_signature"`

	exit bool
}

func (r *Request) ToJSON() []byte {
	bs, _ := json.Marshal(r)
	return bs
}

func (r *Request) String() string {
	return string(r.ToJSON())
}

// Answer contains a single answer returned by a DNS server.
type Answer struct {
	Ttl    uint32        `json:"ttl"`
	String string        `json:"string"`
	Record record.Record `json:"record"`
}

// Result contains metadata relating to a set of DNS server results.
type Result struct {
	Request  Request       `json:"request"`
	Duration time.Duration `json:"duration"`
	Answers  []Answer      `json:"answers"`
	Error    error         `json:"error,omitempty"`
}

func (r *Result) ToJSON() []byte {
	bs, _ := json.Marshal(r)
	return bs
}

func (r *Result) String() string {
	return string(r.ToJSON())
}

func (r *Result) ExtractRecords() []record.Record {
	result := make([]record.Record, 0)
	for _, a := range r.Answers {
		result = append(result, a.Record)
	}

	return record.Unique(result)
}

type Results []Result

func (rs *Results) ExtractRecords() *record.Records {
	result := make(record.Records, 0)

	for _, r := range *rs {
		result = append(result, r.ExtractRecords()...)
	}
	result = record.Unique(result)

	return &result
}

// Queue contains methods and state for setting up a request queue.
type Queue struct {
	Requests    chan *Request
	Results     chan *Result
	WorkerCount int
	Quit        chan bool
}

// StartQueue starts a new queue with max length of X with worker count Y.
func StartQueue(size, workers int) *Queue {
	q := &Queue{
		Requests:    make(chan *Request, size),
		Results:     make(chan *Result, size),
		WorkerCount: workers,
	}
	for i := 0; i < q.WorkerCount; i++ {
		go startWorker(q.Requests, q.Results)
	}

	return q
}

// Add Queue.Add adds a request to the queue. Only blocks if queue is full.
func (q *Queue) Add(dest, recordType, recordName string) {
	q.Requests <- &Request{
		Destination: dest,
		RecordType:  recordType,
		RecordName:  recordName,
	}
}

// SendCompletionSignal Queue.SendDieSignal sends a signal to the workers that they can go home now.
func (q *Queue) SendCompletionSignal() {
	logger.L.Infof("Sending completion signal...")
	for i := 0; i < q.WorkerCount; i++ {
		q.Requests <- &Request{exit: true}
	}
}

// startWorker starts a thread to watch the request channel and populate result channel.
func startWorker(queue <-chan *Request, results chan<- *Result) {
	for request := range queue {
		if request.exit {
			logger.L.Infof("Completion received, worker is done.")
			return
		}
		result, err := SendQuery(request)
		if err != nil {
			logger.L.Errorf("Error sending query: %s", err)
		}
		logger.L.Infof("Sending back result: %s", result.String())
		results <- &result
	}
}

// SendQuery Send a DNS query via UDP, configured by a Request object. If successful,
// stores response details in Result object, otherwise, returns Result object
// with an error string.
func SendQuery(request *Request) (Result, error) {
	result := Result{}

	logger.L.Debugf("Sending query: %s", request)
	result.Request = *request

	recordType, ok := dns.StringToType[request.RecordType]
	if !ok {
		result.Error = fmt.Errorf("Invalid type: %s", request.RecordType)
		return result, result.Error
	}

	m := new(dns.Msg)
	if request.VerifySignature == true {
		logger.L.Debugf("SetEdns0 for %s", request.RecordName)
		m.SetEdns0(4096, true)
	}
	m.SetQuestion(request.RecordName, recordType)
	c := new(dns.Client)
	in, rtt, err := c.Exchange(m, request.Destination)
	// log.Printf("Answer: %s [%d] %s", in, rtt, err)

	result.Duration = rtt
	if err != nil {
		result.Error = err
	} else {
		for _, rr := range in.Answer {
			answer := Answer{
				Ttl:    rr.Header().Ttl,
				String: rr.String(),
				Record: record.Record{
					Type: dns.Type(rr.Header().Rrtype).String(),
					Name: rr.Header().Name,
				},
			}
			result.Answers = append(result.Answers, answer)
		}
	}
	return result, nil
}
