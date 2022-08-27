package logger

import (
	"github.com/onsi/ginkgo/reporters/stenographer/support/go-colorable"
	log "github.com/sirupsen/logrus"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"time"
)

var L *zap.SugaredLogger

// Init -initializes the logger, different in test and production, call after config.Init
func Init(isProductionMode ...bool) {
	if len(isProductionMode) > 0 && isProductionMode[0] {
		zc, err := zap.NewProduction()
		if err != nil {
			panic(err)
		}
		L = zc.Sugar()
		return
	}

	zc := zap.NewDevelopmentEncoderConfig()
	zc.EncodeLevel = zapcore.CapitalColorLevelEncoder
	zc.EncodeTime = zapcore.TimeEncoderOfLayout(time.RFC850)
	L = zap.New(zapcore.NewCore(
		zapcore.NewConsoleEncoder(zc),
		zapcore.AddSync(colorable.NewColorableStdout()),
		zapcore.DebugLevel,
	)).Sugar()
}

func Fatal(args ...interface{}) {
	if L == nil {
		log.Fatalln(args)
	}

	L.Fatal(args)
}

func Info(args ...interface{}) {
	if L == nil {
		log.Infoln(args)
		return
	}

	L.Info(args)
}

func Warn(args ...interface{}) {
	if L == nil {
		log.Warnln(args)
		return
	}

	L.Warn(args)
}

func Debug(args ...interface{}) {
	if L == nil {
		log.Debugln(args)
		return
	}

	L.Debug(args)
}

func Error(args ...interface{}) {
	if L == nil {
		log.Errorln(args)
		return
	}

	L.Error(args)
}
