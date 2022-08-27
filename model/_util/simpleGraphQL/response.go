package simpleGraphQL

type GraphQLResponse struct {
	QueryIds []string `json:"query_ids"`
	Results  []Result `json:"results"`
}

type Result struct {
	QueryId    string       `json:"query_id"`
	Status     string       `json:"status"`
	Columns    Column       `json:"columns"`
	DataPoints []DataPoints `json:"datapoints"`
}

type Column struct {
	Aggregations []string `json:"aggregations"`
	BreakDowns   []string `json:"breakdowns"`
}

type DataPoints struct {
	Timestamp int64    `json:"timestamp"`
	Rows      []Column `json:"rows"`
}
