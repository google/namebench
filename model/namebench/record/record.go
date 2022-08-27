package record

import (
	"fmt"
	"strings"
)

type Record struct {
	Type string `json:"type"`
	Name string `json:"name"`
}

func (r *Record) String() string {
	return fmt.Sprintf("%s", r.Name)
}

func New() *Record {
	return &Record{}
}

type Records []Record

func (rs *Records) String() string {
	return rs.StringWith("\n")
}

func (rs *Records) StringWith(joinStr string) string {
	result := make([]string, 0)
	for _, r := range *rs {
		result = append(result, r.String())
	}

	return strings.Join(result, joinStr)
}
