package simpleGraphQL

import "strconv"

func GetLatestDataPoints(dps []DataPoints) *DataPoints {
	if len(dps) == 0 {
		return nil
	}
	curr := &dps[0]

	for _, dp := range dps {
		if dp.Timestamp >= curr.Timestamp {
			curr = &dp
		}
	}

	return curr
}

func SplitActiveUser(column Column) (int64, int64, int64, error) {
	mauStr := column.Aggregations[0]
	wauStr := column.Aggregations[1]
	dauStr := column.Aggregations[2]

	mau, err := strconv.Atoi(mauStr)
	if err != nil {
		return -1, -1, -1, err
	}
	wau, err := strconv.Atoi(wauStr)
	if err != nil {
		return -1, -1, -1, err
	}
	dau, err := strconv.Atoi(dauStr)
	if err != nil {
		return -1, -1, -1, err
	}

	return int64(mau), int64(wau), int64(dau), nil
}

func CheckAllCompletedQL(response *GraphQLResponse) bool {
	results := response.Results

	for _, r := range results {
		if r.Status != "complete" {
			return false
		}
	}

	return true
}
