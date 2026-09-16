import numpy as np

def calculate_stage5_accuracy(y_true, y_pred, paper_target_acc):
    """
    Stage 5: Execution & Validation Sandbox Accuracy Check
    Calculates test accuracy, delta relative to paper benchmark, and pass status.
    """
    # Calculate test accuracy
    correct_predictions = np.sum(np.array(y_true) == np.array(y_pred))
    total_samples = len(y_true)
    calculated_acc = correct_predictions / total_samples

    # Calculate metric delta against paper benchmark
    metric_delta = abs(calculated_acc - paper_target_acc) * 100
    
    # 5% tolerance threshold check as per MRep validation rules
    status = "PASS" if metric_delta <= 5.0 else "FAIL"

    print("=" * 45)
    print("      MREP STAGE 5 VALIDATION LOG")
    print("=" * 45)
    print(f"Calculated Test Accuracy : {calculated_acc:.4f} ({calculated_acc*100:.2f}%)")
    print(f"Paper Ground Truth Target: {paper_target_acc:.4f} ({paper_target_acc*100:.2f}%)")
    print(f"Metric Delta             : {metric_delta:.2f}%")
    print(f"Tolerance Threshold      : 5.0%")
    print(f"Status                   : {status}")
    print("=" * 45)

    return calculated_acc, status

if __name__ == "__main__":
    # Example ground truth labels vs predicted labels
    y_true_sample = [0, 1, 1, 0, 2, 1, 0, 2, 1, 0]
    y_pred_sample = [0, 1, 1, 0, 2, 1, 0, 2, 0, 0] # 9/10 correct = 0.90
    paper_target = 0.9050  # Target from paper

    calculate_stage5_accuracy(y_true_sample, y_pred_sample, paper_target)