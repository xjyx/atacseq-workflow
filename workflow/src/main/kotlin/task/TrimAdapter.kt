package task

import krews.core.CacheIgnored
import krews.core.WorkflowBuilder
import krews.file.OutputFile
import model.*
import org.reactivestreams.Publisher

data class TrimAdapterParams(
        val minTrimLen: Int = 5,
        val errRate: Double = 0.1,
        @CacheIgnored val numThreads: Int = 1
)

data class TrimAdapterInput(
        val rep: FastqReplicate
)

data class TrimAdapterOutput(
        val mergedReplicate: MergedFastqReplicate
)

fun WorkflowBuilder.trimAdapterTask(i: Publisher<TrimAdapterInput>) = this.task<TrimAdapterInput, TrimAdapterOutput>("trim-adapter", i) {
    val params = taskParams<TrimAdapterParams>()

    dockerImage = "genomealmanac/atacseq-trim-adapters:1.0.3"

    val rep = input.rep
    output =
            if (input.rep is FastqReplicateSE) {
                val merged = MergedFastqReplicateSE(name = rep.name, merged = OutputFile("trim/${rep.name}.merged.fastq.gz"))
                TrimAdapterOutput(merged)
            } else {
                val merged = MergedFastqReplicatePE(
                        name = rep.name,
                        mergedR1 = OutputFile("trim/${rep.name}.R1.merged.fastq.gz"),
                        mergedR2 = OutputFile("trim/${rep.name}.R2.merged.fastq.gz")
                )
                TrimAdapterOutput(merged)
            }

    val detectAdaptor = (rep is FastqReplicateSE && rep.adaptor == null) ||
            (rep is FastqReplicatePE && (rep.adaptorR1 == null || rep.adaptorR2 == null))
    command =
            """
            /app/encode_trim_adapter.py \
                --out-dir $dockerDataDir/trim \
                --output-prefix ${rep.name} \
                ${if (rep is FastqReplicateSE) "--fastqs ${rep.fastqs.joinToString(" ") { it.dockerPath }}" else ""} \
                ${if (rep is FastqReplicateSE && !detectAdaptor) "--adapter ${rep.adaptor!!.dockerPath}" else ""} \
                ${if (rep is FastqReplicatePE) "--fastqs-r1 ${rep.fastqsR1.joinToString(" ") { it.dockerPath }}" else ""} \
                ${if (rep is FastqReplicatePE) "--fastqs-r2 ${rep.fastqsR2.joinToString(" ") { it.dockerPath }}" else ""} \
                ${if (rep is FastqReplicatePE && !detectAdaptor) "--adapter-r1 ${rep.adaptorR1!!.dockerPath}" else ""} \
                ${if (rep is FastqReplicatePE && !detectAdaptor) "--adapter-r2 ${rep.adaptorR2!!.dockerPath}" else ""} \
                ${if (detectAdaptor) "--auto-detect-adapter" else ""} \
                --min-trim-len ${params.minTrimLen} \
                --err-rate ${params.errRate} \
                --nth ${params.numThreads}
            """
}