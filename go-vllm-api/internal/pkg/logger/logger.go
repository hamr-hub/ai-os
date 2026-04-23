package logger

import (
	"os"
	"path/filepath"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

func NewLogger(logDir string) *zap.Logger {
	encoderCfg := zap.NewProductionEncoderConfig()
	encoderCfg.TimeKey = "timestamp"
	encoderCfg.EncodeTime = zapcore.ISO8601TimeEncoder
	encoderCfg.EncodeLevel = zapcore.CapitalLevelEncoder

	consoleEncoder := zapcore.NewConsoleEncoder(encoderCfg)

	consoleCore := zapcore.NewCore(
		consoleEncoder,
		zapcore.AddSync(os.Stdout),
		zapcore.DebugLevel,
	)

	var cores []zapcore.Core = []zapcore.Core{consoleCore}

	if logDir != "" {
		if err := os.MkdirAll(logDir, 0755); err == nil {
			fileEncoderCfg := encoderCfg
			fileEncoderCfg.EncodeLevel = zapcore.CapitalLevelEncoder
			fileEncoder := zapcore.NewJSONEncoder(fileEncoderCfg)

			logFile := filepath.Join(logDir, "app-controller.log")
			f, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
			if err == nil {
				fileCore := zapcore.NewCore(
					fileEncoder,
					zapcore.AddSync(f),
					zapcore.InfoLevel,
				)
				cores = append(cores, fileCore)
			}
		}
	}

	core := zapcore.NewTee(cores...)
	return zap.New(core, zap.AddCaller(), zap.AddStacktrace(zapcore.ErrorLevel))
}
