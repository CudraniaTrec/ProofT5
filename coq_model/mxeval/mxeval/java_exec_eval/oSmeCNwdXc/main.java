import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class FrequencyOfLargest{
  public static Integer frequencyOfLargest(int n, List<Integer> arr){
    int max = arr.get(0);
    int freq = 1;
    for (int i = 1; i < n; i++){
      if (arr.get(i) > max){
        max = arr.get(i);
        freq = 1;
      } else {
        if (arr.get(i) == max){
          freq++;
        }
      }
    }
    return freq;
  }
}

class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        int arg00 = 5;
        List<Integer> arg01 = Arrays.asList(1, 2, 3, 4, 4);
        int x0 = FrequencyOfLargest.frequencyOfLargest(5, Arrays.asList(1, 2, 3, 4, 4));
        int v0 = 2;
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        int arg10 = 3;
        List<Integer> arg11 = Arrays.asList(5, 6, 5);
        int x1 = FrequencyOfLargest.frequencyOfLargest(3, Arrays.asList(5, 6, 5));
        int v1 = 1;
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        int arg20 = 4;
        List<Integer> arg21 = Arrays.asList(2, 7, 7, 7);
        int x2 = FrequencyOfLargest.frequencyOfLargest(4, Arrays.asList(2, 7, 7, 7));
        int v2 = 3;
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
