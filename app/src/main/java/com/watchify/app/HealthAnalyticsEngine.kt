package com.watchify.app

object HealthAnalyticsEngine {
    
    data class MetricAnalysis(
        val metricName: String,
        val status: String, // "Under", "Normal", "Above"
        val message: String,
        val value: Float,
        val maxScore: Int,
        val scoreEarned: Int
    )

    fun analyzeAll(
        hrValues: List<Float>,
        bpSys: List<Float>,
        bpDia: List<Float>,
        spo2Values: List<Float>,
        bgValues: List<Float>,
        sleepValues: List<Float>,
        tempValues: List<Float>
    ): Pair<Int, List<MetricAnalysis>> {
        val analysisList = mutableListOf<MetricAnalysis>()
        var totalScore = 0
        var maxPossible = 0

        // HR (60 - 100)
        if (hrValues.isNotEmpty()) {
            val hr = hrValues.average().toFloat()
            maxPossible += 20
            var score = 20
            var status = "Normal"
            var msg = "Heart rate is optimal."
            if (hr < 50) { score -= 10; status = "Under"; msg = "Bradycardia. Heart rate is very low." }
            else if (hr > 100) { score -= 10; status = "Above"; msg = "Tachycardia. Heart rate is high." }
            totalScore += score
            analysisList.add(MetricAnalysis("Heart Rate", status, msg, hr, 20, score))
        }
        
        // BP (Sys: 90-120, Dia: 60-80)
        if (bpSys.isNotEmpty() && bpDia.isNotEmpty()) {
            val sys = bpSys.average().toFloat()
            val dia = bpDia.average().toFloat()
            maxPossible += 20
            var score = 20
            var status = "Normal"
            var msg = "Blood pressure is in a healthy range."
            if (sys > 130 || dia > 85) { score -= 15; status = "Above"; msg = "High blood pressure (Hypertension)." }
            else if (sys < 90 || dia < 60) { score -= 10; status = "Under"; msg = "Low blood pressure (Hypotension)." }
            totalScore += score
            analysisList.add(MetricAnalysis("Blood Pressure", status, msg, sys, 20, score))
        }

        // SpO2 (95-100)
        if (spo2Values.isNotEmpty()) {
            val spo2 = spo2Values.average().toFloat()
            maxPossible += 20
            var score = 20
            var status = "Normal"
            var msg = "Oxygen levels are excellent."
            if (spo2 < 95) { score -= 15; status = "Under"; msg = "Low oxygen levels. Hypoxemia risk." }
            totalScore += score
            analysisList.add(MetricAnalysis("Blood Oxygen", status, msg, spo2, 20, score))
        }

        // BG (4.0 - 7.8)
        if (bgValues.isNotEmpty()) {
            val bg = bgValues.average().toFloat()
            maxPossible += 20
            var score = 20
            var status = "Normal"
            var msg = "Blood glucose is balanced."
            if (bg > 8.0) { score -= 15; status = "Above"; msg = "Hyperglycemia. Sugar levels are high." }
            else if (bg < 3.9) { score -= 15; status = "Under"; msg = "Hypoglycemia. Sugar levels are low." }
            totalScore += score
            analysisList.add(MetricAnalysis("Blood Glucose", status, msg, bg, 20, score))
        }

        // Body Temp (36.1 - 37.2)
        if (tempValues.isNotEmpty()) {
            val temp = tempValues.average().toFloat()
            maxPossible += 20
            var score = 20
            var status = "Normal"
            var msg = "Body temperature is optimal."
            if (temp > 37.5) { score -= 15; status = "Above"; msg = "Fever detected. Temperature is high." }
            else if (temp < 35.5) { score -= 15; status = "Under"; msg = "Hypothermia risk. Temperature is low." }
            totalScore += score
            analysisList.add(MetricAnalysis("Body Temp", status, msg, temp, 20, score))
        }

        val normalizedScore = if (maxPossible == 0) 100 else (totalScore * 100) / maxPossible
        return Pair(normalizedScore, analysisList)
    }
}
