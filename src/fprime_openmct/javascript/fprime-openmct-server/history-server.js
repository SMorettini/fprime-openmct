var express = require('express');

function HistoryServer(telemetry) {
    var router = express.Router();

    router.get('/:pointId', function (req, res) {
        var start = +req.query.start;
        var end = +req.query.end;
        var ids = req.params.pointId.split(',');

        // #Problem if history is empty since there is not anymore the default value
        var response = ids.reduce(function (resp, id) {
            var historyData = telemetry.history[id]?.filter(function (p) {
                return p.timestamp > start && p.timestamp < end;
            }) || [];
            // Concatenate the filtered data to the response
            return resp.concat(historyData);
        }, []);
        res.status(200).json(response).end();
    });

    return router;
}

module.exports = HistoryServer;

