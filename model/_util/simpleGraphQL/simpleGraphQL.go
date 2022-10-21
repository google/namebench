package simpleGraphQL

import (
	"strconv"
	"time"
)

type GraphQLQuery struct {
	FilterSet         string   `json:"filter_set"`
	Since             int64    `json:"since"`
	Source            string   `json:"source"`
	Until             int64    `json:"until"`
	SectionLoadId     string   `json:"section_load_id"`
	AggregationPeriod string   `json:"aggregation_period"`
	Aggregations      []string `json:"aggregations"`
	Breakdowns        []string `json:"breakdowns"`
	EventName         string   `json:"event_name"`
	MetricParams      EmptyMap `json:"metric_params"`
	OrderingColumns   *string  `json:"ordering_columns"`
	Retry             bool     `json:"retry"`
}

type EmptyMap struct {
}

func New() *GraphQLQuery {
	return &GraphQLQuery{}
}
func NewBasic() *GraphQLQuery {
	ql := New()

	// Getting Until & Since time first.
	untilTs := time.Now()
	untilHour := (untilTs.Unix() / 3600) + 1 - 36
	until := untilHour * 3600
	//since := until - 2332800
	since := int64(1560322800) // Since will be LifeTime (When Data has been started to insert in Facebook Marketing Service)

	//Preparing Variables
	breakDowns := make([]string, 0)

	// Inputting Base Data
	ql.FilterSet = "{}"
	ql.Since = since
	//ql.Source = "www/appevents"
	ql.Until = until
	ql.SectionLoadId = "f26c03db-f8b7-4e4e-b153-0d01f9ebead3" //"4959e913-eebd-4f91-a0f3-1dace401444f"
	//ql.AggregationPeriod = "range"
	//ql.Aggregations = aggregations
	ql.Breakdowns = breakDowns
	//ql.EventName = "fb_mobile_first_app_launch"
	ql.MetricParams = EmptyMap{}
	ql.OrderingColumns = nil
	ql.Retry = false

	return ql
}

func DPRowsToMap(columns []Column) (map[string]int64, error) {
	r := make(map[string]int64)

	for _, c := range columns {
		b := c.BreakDowns[0]
		v, err := strconv.Atoi(c.Aggregations[0])
		if err != nil {
			return nil, err
		}
		r[b] = int64(v)
	}

	return r, nil
}

//
//func (g *GraphQLQuery) Create() error {
//
//}
