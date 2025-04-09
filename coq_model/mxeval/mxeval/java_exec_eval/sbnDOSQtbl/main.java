import java.io.*;
import java.lang.*;
import java.util.*;
import java.math.*;
class MaxOccurrences {
    public static List<Integer> maxOccurrences(List<Integer> nums) {
        int max = 0;
        int max_occ = 0;
        HashMap<Integer, Integer> occ = new HashMap<>();
        for ( int i : nums ) {
            if ( occ.containsKey(i) ) {
                occ.put(i, ( occ.get(i) + 1 ));
                } else {
                occ.put(i, 1);
            }
            if ( occ.get(i) > max_occ ) {
                max_occ = occ.get(i);
                max = i;
            }
        }
        List<Integer> result = new ArrayList<>();
        result.add(max);
        result.add(max_occ);
        return result;
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
        List<Integer> arg00 = Arrays.asList(2, 3, 8, 4, 7, 9, 8, 2, 6, 5, 1, 6, 1, 2, 3, 2, 4, 6, 9, 1, 2);
        List<Integer> x0 = MaxOccurrences.maxOccurrences(Arrays.asList(2, 3, 8, 4, 7, 9, 8, 2, 6, 5, 1, 6, 1, 2, 3, 2, 4, 6, 9, 1, 2));
        List<Integer> v0 = Arrays.asList(2, 5);
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<Integer> arg10 = Arrays.asList(2, 3, 8, 4, 7, 9, 8, 7, 9, 15, 14, 10, 12, 13, 16, 16, 18);
        List<Integer> x1 = MaxOccurrences.maxOccurrences(Arrays.asList(2, 3, 8, 4, 7, 9, 8, 7, 9, 15, 14, 10, 12, 13, 16, 16, 18));
        List<Integer> v1 = Arrays.asList(8, 2);
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<Integer> arg20 = Arrays.asList(10, 20, 20, 30, 40, 90, 80, 50, 30, 20, 50, 10);
        List<Integer> x2 = MaxOccurrences.maxOccurrences(Arrays.asList(10, 20, 20, 30, 40, 90, 80, 50, 30, 20, 50, 10));
        List<Integer> v2 = Arrays.asList(20, 3);
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
